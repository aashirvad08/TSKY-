from dataclasses import dataclass


class PhoenixCommsModel:

    def __init__(self):

        print("Deploying TSKY Inter-Satellite Network v2.0...")

        # ==============================================
        # NETWORK CONFIG
        # ==============================================

        self.MAX_BANDWIDTH_GBPS = 40.0

        self.network_health_pct = 100.0

        self.total_data_transferred_gb = 0.0

    # ==============================================
    # AGING MODEL
    # ==============================================

    def _apply_degradation(
        self,
        mission_elapsed_days
    ):

        years = mission_elapsed_days / 365.25

        self.network_health_pct = max(
            90.0,
            100.0 - years * 0.5
        )

    # ==============================================
    # LINK STATE
    # ==============================================

    def _determine_link_state(
        self,
        link_quality
    ):

        if link_quality > 80:
            return "NOMINAL"

        if link_quality > 50:
            return "DEGRADED"

        if link_quality > 20:
            return "RECOVERY"

        return "LOST"

    # ==============================================
    # MAIN UPDATE
    # ==============================================

    def update_telemetry(

        self,

        satellite_distance_km,

        antenna_alignment_pct,

        data_volume_gb,

        network_congestion_pct,

        mission_elapsed_days

    ):

        self._apply_degradation(
            mission_elapsed_days
        )

        distance_factor = max(

            0.1,

            1.0 -
            (
                satellite_distance_km /
                10000.0
            )

        )

        alignment_factor = (
            antenna_alignment_pct /
            100.0
        )

        congestion_factor = max(
            0.0,
            1.0 -
            (
                network_congestion_pct /
                100.0
            )
        )

        health_factor = (
            self.network_health_pct /
            100.0
        )

        link_quality = (

            distance_factor *

            alignment_factor *

            congestion_factor *

            health_factor

        ) * 100.0

        bandwidth_gbps = (

            self.MAX_BANDWIDTH_GBPS *

            (link_quality / 100.0)

        )

        latency_ms = (

            1.0 +

            satellite_distance_km /
            300.0

        )

        packet_loss_pct = max(
            0,
            5.0 - (
                link_quality / 20.0
            )
        )

        transfer_time_sec = (

            (data_volume_gb * 8.0)

            /

            max(
                bandwidth_gbps,
                0.001
            )

        )

        self.total_data_transferred_gb += (
            data_volume_gb
        )

        return {

            "link_quality_pct":
                round(
                    link_quality,
                    2
                ),

            "latency_ms":
                round(
                    latency_ms,
                    2
                ),

            "bandwidth_gbps":
                round(
                    bandwidth_gbps,
                    2
                ),

            "packet_loss_pct":
                round(
                    packet_loss_pct,
                    2
                ),

            "network_health_pct":
                round(
                    self.network_health_pct,
                    2
                ),

            "recommended_link_state":
                self._determine_link_state(
                    link_quality
                ),

            "transfer_time_sec":
                round(
                    transfer_time_sec,
                    2
                ),

            "total_data_transferred_gb":
                round(
                    self.total_data_transferred_gb,
                    2
                )
        }