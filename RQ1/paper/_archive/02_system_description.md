# 2. System description

_All ten air-path topologies share the same drying chamber, the same R134a vapour-compression cycle, the same flat-plate solar air collector model, the same counter-flow plate heat-recovery exchanger (HRX) where applicable, and the same VPD-triggered exhaust bypass valve. They differ only in how the four thermodynamic blocks (ambient inlet, solar collector, condenser, evaporator) and the optional HRX are connected. This section describes the topology of each variant. Component-level equations, refrigerant-side relations, and the kinetic and psychrometric submodels are deferred to §3._

[Figure 2.1: Master schematic of the reference dryer (Config A). Shows the drying chamber with ten loaded trays, the R134a heat-pump loop with condenser on the supply side and evaporator on the return side, the ambient inlet, the chamber exhaust port, the VPD-triggered exhaust bypass valve, and the recirculation duct. All other configurations are obtained by inserting or rerouting the solar collector and/or the HRX into this base topology.]

## 2.1 Reference configuration (Config A, HP-only)

Config A is the heat-pump-only reference against which the nine variants are benchmarked. Ambient air enters the system, passes through the condenser where it is heated to the chamber set-point T_set = 45 °C, traverses the loaded chamber, picks up moisture from the apple slices, and is partly recirculated and partly discharged. At the open-loop limit (recirculation fraction r = 0) the evaporator runs on an independent ambient draw and is decoupled from the heating stream. At r > 0 the recirculated exhaust is mixed with fresh ambient and routed first through the evaporator (where it is dehumidified and cooled) and then through the condenser (where it is reheated to T_set). The first-law constraint Q_cond = Q_evap + W_comp is enforced on every time step, and the compressor speed is sized so that the condenser-side air leaves at exactly T_set.

## 2.2 Solar-assisted variants (Configs B, C1, C2)

Three configurations introduce a flat-plate solar air collector of area A_c (the baseline value used throughout the paper is A_c = 10 m²) into the heating side of the system.

**Config B** places the collector in series with the condenser on the supply line. At r = 0 the path is Amb → Sol → Cond → Cham → Exh → Discharge, with the evaporator running on a parallel ambient draw. At r > 0 the recirculated exhaust is mixed with ambient, passes through the evaporator, then the collector, then the condenser. B is the most direct analogue of Hawlader (2003) and Şevik (2013).

**Config C1** is a solar cascade with the evaporator placed _inline_ between collector and condenser. The path at r = 0 is Amb → Sol → Evap → Cond → Cham → Exh → Discharge. The collector preheat is therefore partially undone by the dehumidifying evaporator before the condenser reheats the stream. This topology is included deliberately to quantify the thermal penalty of running the evaporator inline, a configuration that appears in some commercial schematics but has rarely been benchmarked against the parallel-evaporator alternative.

**Config C2** is a solar cascade with mixing _after_ the collector. At r = 0 the topology splits into two parallel streams: a heating path Amb → Cond → Cham → Exh → Discharge and a separate cooling path Sol → Evap → Discharge. At r > 0 the collector feeds the recirculation mix node so that solar heat is delivered to the evaporator inlet rather than to the condenser supply. The r = 0 case must be drawn with two clearly separate paths; the source-code behaviour is the authoritative reference for this configuration.

[Figure 2.2: Block-diagram grid of the nine non-reference air paths (B, C1, C2, D1, D2, D3, E1, E2, E3). Each panel uses the same icon set; arrows indicate flow direction; recirculation paths (where applicable) are drawn dashed.]

## 2.3 Heat-recovery variants (Configs D1, D2, D3)

Three configurations introduce a counter-flow plate HRX with effectiveness ε = 0.70 between the chamber exhaust and the ambient inlet. All three are open-loop (r = 0 by design) and have no solar collector.

**Config D1** routes ambient air through the cold side of the HRX, then through the condenser, then into the chamber. The exhaust passes through the hot side of the HRX and is then expelled. The evaporator runs on a separate ambient draw.

**Config D2** uses the same heating-side path as D1, but the evaporator is fed by the exhaust leaving the HRX hot side. A dynamic ambient supplement is added to the evaporator inlet so that the evaporator load matches the condenser duty under the first-law constraint.

**Config D3** is included as an inversion test: the chamber exhaust is sent to the cold side of the HRX, then to the condenser and into the chamber, while the ambient draw is sent to the hot side and then to the evaporator. This routing recovers latent heat into the supply but also recycles humid air back into the chamber, and is reported here mainly to demonstrate that the resulting humidity penalty is observable in the SEC results.

## 2.4 Combined variants (Configs E1, E2, E3)

The E group combines HRX heat recovery with solar preheat. All three are r = 0 by design; the open-loop, HRX-equipped supply removes most of the energy benefit of recirculation and would also raise the chamber humidity unnecessarily.

**Config E1** places ambient air through the HRX cold side, then the collector, then the condenser, then the chamber. The chamber exhaust passes through the HRX hot side and is discharged. The evaporator runs on an independent ambient draw, so dehumidification is fully decoupled from the heating stream.

**Config E2** uses the same heating-side path as E1, but the chamber exhaust is split: one portion gives heat back through the HRX hot side and is discharged, and the second portion is mixed with an ambient supplement and fed to the evaporator. The supplement mass flow is solved by a fixed-point iteration so that the evaporator load matches the condenser duty exactly. The recovered exhaust raises the evaporator inlet temperature and humidity, which raises COP. E2 is the best-performing topology in the present study.

**Config E3** moves the collector _downstream_ of the condenser: ambient → HRX cold side → condenser → collector → chamber. A solar-priority control overlay is applied. If the post-collector air alone reaches T_set, the heat pump is switched off and the collector finishes the temperature lift. Otherwise the heat pump runs at a variable condenser temperature chosen so that the post-collector stream meets T_set exactly, and the collector tops up the residual lift. The exhaust-side handling is identical to E2 (split between HRX recovery and evaporator supply with iterative ambient supplement).

## 2.5 VPD-triggered exhaust bypass control

A single control overlay is applied uniformly to all ten configurations: a VPD-triggered exhaust bypass valve. Vapour-pressure deficit (VPD) at the chamber outlet is monitored on every time step. When VPD falls below a threshold of 0.05 kPa (set so that mass-transfer driving force, not heat input, becomes the limiting resistance), the bypass opens and a portion of the recirculated stream is dumped to ambient and replaced with fresh dry intake. The valve uses 3× hysteresis (it must clear 3 × 0.05 = 0.15 kPa before closing) and a 600 s dwell time to suppress oscillation. The same trigger logic and the same threshold are used across all ten configs so that the bypass effect can be compared cleanly with the topology effect.

[Figure 2.3: VPD-bypass control logic. State diagram with two states (bypass closed / bypass open); transitions labelled with the VPD threshold, hysteresis multiplier, and dwell timer. A second panel shows a representative chamber-outlet VPD trace over a single batch with the bypass open/closed regions shaded.]

The bypass valve is the only active control element shared by all ten configurations. Compressor speed (sized to deliver T_set at the condenser outlet), evaporator-side ambient supplement (D2, E2, E3), and the solar-priority HP on/off switch (E3 only) are configuration-specific control elements and are described together with the topology of the relevant variant above.
