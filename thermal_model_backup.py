import math

class DistributedNodeThermalModel:
    def __init__(self):
        """
        TSKY Orbital Data Center - 20-Node Granular Thermal Engine.
        Tracks thermodynamics for individual GPU racks via Smart Manifold routing.
        """
        print("Deploying TSKY 20-Node Smart Manifold Thermal Core...")

        self.NUM_NODES = 20
        
        # =========================================================
        # NODE-LEVEL SPECIFICATIONS
        # =========================================================
        # 800 kg total / 20 nodes = 40 kg per node
        self.NODE_MASS_KG = 40.0       
        self.NODE_SPECIFIC_HEAT = 400.0    
        self.NODE_THERMAL_MASS = self.NODE_MASS_KG * self.NODE_SPECIFIC_HEAT
        
        self.NODE_MAX_COMPUTE_W = 3900.0       # 3.9 kW max peak per node (78kW total)
        self.GPU_CRITICAL_TEMP_C = 85.0        
        
        # Track 20 individual temperatures (starting at 15°C)
        self.node_temps_c = [15.0 for _ in range(self.NUM_NODES)]

        # =========================================================
        # MACRO SYSTEM SPECIFICATIONS (Hull, Radiators, PCM)
        # =========================================================
        self.RADIATOR_AREA_M2 = 210.0          
        self.RADIATOR_EMISSIVITY = 0.95        
        self.STEFAN_BOLTZMANN = 5.67e-8
        
        self.HULL_MASS_KG = 550.0              
        self.HULL_THERMAL_MASS = self.HULL_MASS_KG * 900.0
        self.hull_temp_c = 15.0

        self.AMMONIA_LATENT_HEAT_J_KG = 1371000.0 
        self.PUMP_NOMINAL_FLOW_KG_S = 0.45        
        
        self.PCM_TOTAL_CAPACITY_J = 1000.0 * 240000.0 # 240 Megajoules
        self.PCM_MELT_POINT_C = 62.0           
        self.pcm_joules_absorbed = 0.0
        self.is_hardware_damaged = False

    def update_telemetry(self, is_sunlit: bool, node_workloads_kw: list, pump_health_pct: float, sim_seconds: float) -> dict:
        """
        :param node_workloads_kw: A list of 20 floats, representing the kW draw of each specific node.
        """
        if len(node_workloads_kw) != self.NUM_NODES:
            raise ValueError("Must provide exactly 20 workload values.")

        # ---------------------------------------------------------
        # 1. MACRO COOLING CAPACITY (The available budget)
        # ---------------------------------------------------------
        # Total heat the radiators shoot into space
        radiator_rejection_w = self.RADIATOR_EMISSIVITY * self.STEFAN_BOLTZMANN * self.RADIATOR_AREA_M2 * (math.pow(self.hull_temp_c + 273.15, 4) - math.pow(3.0, 4))
        
        # Total heat the pump can physically transport
        active_flow_kg_s = self.PUMP_NOMINAL_FLOW_KG_S * pump_health_pct
        max_transportable_w = active_flow_kg_s * self.AMMONIA_LATENT_HEAT_J_KG
        
        # Total system cooling budget for this tick
        effective_cooling_w = min(radiator_rejection_w, max_transportable_w)
        total_cooling_j = effective_cooling_w * sim_seconds

        # ---------------------------------------------------------
        # 2. SMART MANIFOLD DISTRIBUTION
        # ---------------------------------------------------------
        # To route cooling, the manifold looks at how hot each node is relative to the total heat of the cluster.
        # It sends a proportional percentage of the total_cooling_j to the hottest nodes.
        sum_of_temps = sum(max(temp, 1.0) for temp in self.node_temps_c) # Prevent div by zero
        
        total_heat_spill_j = 0.0 # Heat that escapes individual nodes into the macro hull

        for i in range(self.NUM_NODES):
            # A. Heat Generation for this specific node
            node_heat_j = (node_workloads_kw[i] * 1000.0) * sim_seconds
            
            # B. Cooling Distribution for this specific node
            cooling_share_pct = max(self.node_temps_c[i], 1.0) / sum_of_temps
            node_cooling_j = total_cooling_j * cooling_share_pct
            
            # C. Net Node Thermodynamics
            net_node_j = node_heat_j - node_cooling_j
            
            # Allow excess heat (or cooling) to bleed into the hull/PCM matrix
            bleed_factor = 0.15 # 15% of net thermal energy transfers to the macro structure
            heat_to_hull = net_node_j * bleed_factor
            total_heat_spill_j += heat_to_hull
            
            heat_kept_in_node = net_node_j - heat_to_hull
            self.node_temps_c[i] += (heat_kept_in_node / self.NODE_THERMAL_MASS)
            
            # Check for critical damage per node
            if self.node_temps_c[i] >= self.GPU_CRITICAL_TEMP_C:
                self.is_hardware_damaged = True
                
            self.node_temps_c[i] = max(self.node_temps_c[i], -40.0)

        # ---------------------------------------------------------
        # 3. MACRO SYSTEM (Hull, Solar, PCM Buffer)
        # ---------------------------------------------------------
        solar_heat_j = (9800.0 if is_sunlit else 0.0) * sim_seconds
        net_macro_j = total_heat_spill_j + solar_heat_j
        
        # Calculate Average Node Temp to trigger the PCM backup
        avg_node_temp = sum(self.node_temps_c) / self.NUM_NODES

        if net_macro_j > 0 and avg_node_temp >= self.PCM_MELT_POINT_C:
            if self.pcm_joules_absorbed < self.PCM_TOTAL_CAPACITY_J:
                self.pcm_joules_absorbed += net_macro_j
                self.hull_temp_c = self.PCM_MELT_POINT_C
                
                # Cap the nodes from thermal runaway while wax is melting
                self.node_temps_c = [min(t, self.PCM_MELT_POINT_C + 2.0) for t in self.node_temps_c]
            else:
                self.hull_temp_c += (net_macro_j / self.HULL_THERMAL_MASS)
        elif net_macro_j < 0 and self.pcm_joules_absorbed > 0:
            self.pcm_joules_absorbed += net_macro_j
            self.hull_temp_c = self.PCM_MELT_POINT_C
            if self.pcm_joules_absorbed < 0:
                self.pcm_joules_absorbed = 0.0
        else:
            self.hull_temp_c += (net_macro_j / self.HULL_THERMAL_MASS)

        # ---------------------------------------------------------
        # 4. FINAL TELEMETRY PAYLOAD
        # ---------------------------------------------------------
        return {
            # List of 20 individual temperatures for the UI Heatmap
            "node_temperatures_c": [round(t, 1) for t in self.node_temps_c],
            
            "avg_cluster_temp_c": round(avg_node_temp, 1),
            "max_node_temp_c": round(max(self.node_temps_c), 1),
            "radiator_temp_c": round(self.hull_temp_c, 1),
            "pcm_saturation_pct": round((self.pcm_joules_absorbed / self.PCM_TOTAL_CAPACITY_J) * 100, 2),
            "ammonia_flow_kg_s": round(active_flow_kg_s, 3),
            "mission_status": "CRITICAL_NODE_FAILURE" if self.is_hardware_damaged else "NOMINAL"
        }