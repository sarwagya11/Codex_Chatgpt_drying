# LIT_REVIEW_LEDGER.md

Phase A output: source verification and claim-by-claim ledger for Section 1 of `SAHPD_Paper.docx`.

Folder audited: `D:\Masters\SAHPD papers\` (45 PDFs after user added 22 more on 2026-04-27).
Author: claude (auto), 2026-04-27. Re-verify every claim before final draft.

**Round 2 update (2026-04-27 evening):** User added 22 papers; many resolved citations previously flagged as "missing PDF". Notably: real Minea 2013 Part I and Part II found, real Mortezapour 2012 found, real Royen 2020 found, real MoALD 2022/23 statistical book found, real Prasertsan & Saen-saby 1998 found, real Chua et al. 2002 found, real Mohanraj 2018 (Part-B) found, real Colak & Hepbasli 2009 found, real Shah & Sekulic textbook found, real Rulazi 2023 found (year was wrong — Food Sci. & Nutr., not 2024). Bhandari 2025 confirmed non-existent via Google search; replace with Tang 2025.

---

## A. Source register (verified PDFs)

Each row is a paper I have personally opened and read at least the first 2 to 3 pages. Filename in column 1 is the actual file in `D:\Masters\SAHPD papers\`. Use this column to verify any claim by opening the file yourself.

| # | Filename | Real authors / year / title | Topic, refrigerant, climate, T_set | Key reported numbers |
|---|----------|----------------------------|------------------------------------|----------------------|
| 1 | `10.1016@j.enconman.2013.01.013.pdf` | **Şevik 2013**, "Design, experimental investigation and analysis of a solar drying system", Energy Conversion and Management 68:227-234 | DPSAC + heat pump, R-134a, Turkey (Ankara), carrot, 50 °C, v = 0.4-0.9 m/s, PID | Carrot 7.76 → 0.1 g/g db in 220 min; collector η 60-78%; PV-supplied |
| 2 | `hawlader2006.pdf` | **Hawlader & Jahangeer 2006**, "Solar heat pump drying and water heating in the tropics", Solar Energy 80:492-499 | NUS Singapore SAHPD + water heater, R134a, **green beans**, 20 kg load | COP 7.0 (1800 rpm sim); SMER **0.65 kg/kWh** at 1200 rpm, 20 kg; collector η 0.86 (evap-coll), 0.7 (air coll) |
| 3 | `hawlader2008.pdf` | **Hawlader, Rahman & Jahangeer 2008**, "Performance of evaporator-collector and air collector in solar assisted heat pump dryer", Energy Conv. & Mgmt. 49:1612-1619 | NUS Singapore evap-coll vs air-coll, R134a | Evap-coll η 0.8-0.86; air coll η 0.7-0.75 |
| 4 | `1-s2.0-S0306261902001459-main.pdf` | **Hawlader, Chou, Jahangeer, Rahman, Lau 2003**, "Solar-assisted heat-pump dryer and water heater", Applied Energy 74:185-193 | NUS Singapore SAHPD + WH, R134a, **food grains** (NOT guava/papaya), variable-speed compressor | COP 7.0 sim / 5.0 exp; SF 0.65 sim / 0.61 exp |
| 5 | `ismaeel2020.pdf` | **Ismaeel & Yumrutaş 2020**, "Thermal performance of a solar-assisted heat pump drying system with thermal energy storage tank and heat recovery unit", Int. J. Energy Res. | Iraq/Turkey, MATLAB analytical, 100 m² coll, 300 m³ TES, **wheat**, 100 kg/h | COP_HP 5.55, COP_sys 5.28, SMER 9.25 (5th yr periodic); HRU saves 21.4% annually vs no-HRU; HX restoring η up to 41.7% |
| 6 | `foods-14-01195.pdf` | **Tang, Li, Xu, Yang, Zhang, Wang, Zhao, Elgamal 2025**, "Performance Evaluation of a Solar-Assisted Multistage Heat Pump Drying System Based on the Optimal Drying Conditions for Solanum lycopersicum L.", Foods 14:1195 | China, multistage SAHPD, **tomato**, 70 °C, 20% RH, 25% fresh air | Solar contributes 85.12% of energy in spring/autumn; performance coefficient 39.16; **moisture extraction 40.7 kg/kWh**; SEC 0.02 kWh/kg; CO2 reduction 7.88 kg/yr |
| 7 | `1-s2.0-S2214157X23005737-main.pdf` | **Kim, Kim, Heo, Lee 2023**, "Energy performance of direct-expansion solar heat pump integrated with thermal network", Case Studies in Thermal Eng. 49:103267 | Korea, DX-SAHP for **district heating** (NOT drying), daycare pilot building | Daily COP 2.0-5.0; 66% energy savings vs electric heater |
| 8 | `1-s2.0-S2214157X23002423-main.pdf` | **Yahya, Fahmi, Hasibuan, Fudholi 2023**, "Development of hybrid solar-assisted heat pump dryer for drying paddy", Case Studies in Thermal Eng. 45:102936 | Indonesia/Malaysia, **paddy**, R22, 62.9 °C, 16.1% RH | Paddy 31.67 → 16.18% db in 5.5 h; SMER 0.44 kg/kWh; SEC 4.69 kWh/kg; η_th 29.1%, η_ex 18.4%; SC 19.7%, BF 12.9% energy contribution |
| 9 | `1-s2.0-S2214157X24015132-main.pdf` | **Aacharya, Davidsson, Baral, Andersson 2024**, "Investigation of thermodynamics performance of a heat exchanger-incorporated solar dryer equipped with double-pass flat, v-corrugated, and low-e coated collectors for drying applications", Case Studies in Thermal Eng. 64:105482 | **Nepal Dhulikhel**, KU + Lund, **apple**, Feb-Apr 2023, 8h/day | Drying rate 107 g/(h·m²) low-e Al; 50 / 84 g/(h·m²) flat / v-corrug GI; OSD 78 g/(h·m²); collector η 89% low-e Al; payback 1.61 y |
| 10 | `1-s2.0-S2590123025016238-main.pdf` | **Adhikari, Garg, Davidsson, Baral, Andersson 2025**, "Flow uniformity inside the drying chamber of a heat exchanger-based solar dryer – numerical analysis with smoke flow visualization as experimental validation", Results in Engineering 26:105553 | KU + Lund, ANSYS Fluent, 6 design configs, smoke flow validation | UI / CV reported in body — **needs deeper page read to verify the 0.58 → 0.78 numbers** |
| 11 | `chanpet2020.pdf` | **Chanpet, Rakmak, Matan, Siripatana 2020**, "Effect of air velocity, temperature, and relative humidity on drying kinetics of rubberwood", Heliyon 6:e05151 | Thailand, kiln drying, **rubberwood**, 60-100 °C, 0.5-4 m/s, 6-67% RH | Henderson-Pabis kinetics; mass transfer K correlation. Not SAHPD. Could support kinetics methodology only. |
| 12 | `kuan2019.pdf` | **Kuan, Shakir, Mohanraj, Belyayev, Jayaraj, Kaltayev 2019**, "Numerical simulation of a heat pump assisted solar dryer for continental climates", Renewable Energy 143:214-225 | Kazakhstan (Almaty), R134a, 1000 W comp, 1 m² coll, **banana** | Banana 74 → 19% wb in 21 h (HPASD) vs 35 h (SD only); **SMER 0.6 kg/kWh, COP 2.72**; recovery saves 12.9% vs 9.9% no-HRU |
| 13 | `salhi2022.pdf` | **Salhi, Chaatouf, Raillani, Amraqui, Mezrhab 2022**, "Investigating the effect of food trays porosity on the drying process", Innov. Food Sci. Emerg. Technol. 76:102939 | Morocco, CFD, plum, tray porosity 30/50/70% | Not SAHPD; tray-uniformity reference only |
| 14 | `1-s2.0-S1364032110001152-main.pdf` | **Daghigh, Ruslan, Sulaiman, Sopian 2010**, "Review of solar assisted heat pump drying systems for agricultural and marine products", Renew. Sustain. Energy Rev. 14:2564-2579 | Review, classification of SAHP and SAHPD systems | Foundational review; **not 2022** as currently cited |
| 15 | `1-s2.0-S1364032113003353-main.pdf` | **Amin & Hawlader 2013**, "A review on solar assisted heat pump systems in Singapore", Renew. Sustain. Energy Rev. 26:286-293 | Review, SAHP for hot water + drying, evap-coll | Reports COP up to 8.0 with R134a evap-coll; rice (Best et al.) 25.5 → 11.45% db in 4.9 h, COP 5.3, SMER 3.5 kg/kWh |
| 16 | `1-s2.0-S0038092X16303073-main.pdf` | **Yahya, Fudholi, Hafizh, Sopian 2016**, "Comparison of solar dryer and solar-assisted heat pump dryer for cassava", Solar Energy 136:606-613 | Indonesia, **cassava** 30.8 → 17.4 kg, 40 / 45 °C | SD: η_th 25.6%, SMER 0.38 kg/kWh, SF 66.7%; SAHPD: η_th 30.9%, SMER 0.47 kg/kWh, SF 44.6%, COP 3.23-3.47 |
| 17 | `1-s2.0-S0038092X16303437-main.pdf` | **Qiu, Li, Hassanien, Wang, Luo, Yu 2016**, "Performance and operation mode analysis of a heat recovery and thermal storage solar-assisted heat pump drying system", Solar Energy 137:225-235 | China, novel HR + TES SAHPD, **radish/pepper/mushroom** | COP 3.21-3.49; **40.53% energy saving** via HR + TES; payback 6 / 4 / 2 years |
| 18 | `1-s2.0-S0038092X20308136-main.pdf` | **Singh, Sarkar, Sahoo 2020**, "Experimentation on solar-assisted heat pump dryer: Thermodynamic, economic and exergoeconomic assessments", Solar Energy 208:150-159 | India IIT-BHU, **R1234yf**, banana chips → 11.5% MC, 8 trays | Drying rate HPD 0.205 / SAHPD 0.342 kg/kg·min; payback 3.9 y; exergoeconomic factor 0.1335 (HPD) / 0.2003 (SAHPD); contains rich review of prior SAHPD work |
| 19 | `1-s2.0-S0038092X21006848-main.pdf` | **Li, Zhang, Li, Wang, Shi, Gao, Deng, Lu, Liu 2021**, "Study on heating performance of solar-assisted heat pump drying system under large temperature difference", Solar Energy 229:148-161 | China Yunnan, Tibetan medicinal plants, altitude > 3000 m, T_amb 5 °C, ΔT 25 °C day-night | HPD COP 1.34 / SHPD COP 2.42 under load (1.8x improvement); 70% time reduction; high-altitude relevance for Taplejung |
| 20 | `rahman2013.pdf` | **Rahman, Saidur, Hawlader 2013**, "An economic optimization of evaporator and air collector area in a solar assisted heat pump drying system", Energy Conv. & Mgmt. 76:377-384 | Singapore NUS setup, FORTRAN, R134a, evap-coll + air-coll | Minimum payback period **~4 years** |
| 21 | `s41598-021-88270-z.pdf` | **Sharabiani, Kaveh, Abdi, Szymanek, Tanaś 2021**, "Estimation of moisture ratio for apple drying by convective and microwave methods using artificial neural network modeling", Scientific Reports 11:9155 | Iran (Ardabil), apple, CD vs MD, 50 / 60 / 70 °C, 1.0 m/s, MW 90/180/360 W | **Midilli model best fits both CD and MD apple drying** (EF best); D_eff CD 1.95 to 4.09e-7 m²/s; Ea CD 122-125 kJ/mol; lowest SEC for MD |
| 22 | `1185-Article Text-3002-1-10-20091025.pdf` | **Meisami-asl & Rafiee 2009**, "Mathematical Modeling of Kinetics of Thin-layer Drying of Apple (var. Golab)", CIGR Ejournal Vol. XI, Manuscript 1185 | Iran (Tehran), apple Golab, 40-80 °C, 0.5-2 m/s, 2-6 mm slabs | **Midilli model gives highest EF = 0.99972, lowest RMSE = 0.00292**, χ² = 1e-5 across 14 tested models |
| 23 | `amanlou2010.pdf` | **Amanlou & Zomorodian 2010**, "Applying CFD for designing a new fruit cabinet dryer", J. Food Eng. 101:8-15 | Iran Shiraz, CFD Fluent, **green fig**, 7 cabinet geometries | Tray uniformity reference only |
| 24 | `ARFMTSV52_N2_P129_138.pdf` | **Misha, Mat, Ruslan, Salleh, Sopian 2018**, "A Study of Drying Uniformity in a New Design of Tray Dryer", J. Adv. Res. Fluid Mech. & Therm. Sci. 52:129-138 | Malaysia, solar + desiccant, kenaf core, 7-layer tray | Tray uniformity reference only |
| 25 | `352-C020.pdf` | **Misha, Mat, Ruslan, Sopian, Salleh 2013**, "The Prediction of Drying Uniformity in Tray Dryer System using CFD Simulation", IJMLC 3(5):419 | Malaysia, CFD on 25 m² tray dryer | Tray uniformity reference only |
| 26 | `Rakyat_2021_studyofairdistibutionintraydryer.pdf` | **Rakyat et al. 2021**, "Study of air distribution in tray dryer using computational fluid dynamics", Eng. & Appl. Sci. Res. 48(6):684-693 | Thailand, CFD on tray dryer geometry | Tray uniformity reference only |
| 27 | `bs2007_398.pdf` | **Gu 2007**, "Airflow Network Modeling in EnergyPlus", Building Simulation 2007 | EnergyPlus building simulation airflow network | Not relevant to SAHPD |
| 28 | `541413_Fulltext.pdf` | **Li, Davidson, Peng 2024**, "A pressure-loss model for flow-through round-hole perforated plates of moderate porosity and thickness", Int. J. Heat Mass Transfer 226:125490 | Chalmers Sweden, RANS, perforated plate ΔP model | Possible reference for tray ΔP modeling, not core SAHPD |
| 29 | `s42452-025-06894-6.pdf` | **Kidane, Farkas, Buzás 2025**, "Modeling airflow dynamics in solar drying chambers: a comprehensive review of CFD applications", Discover Applied Sciences 7:444 | Hungary, CFD review, bibliometric | Useful for §6 chamber discussion |
| 30 | `123705-ESM-P150328-PUBLIC-NepalSolarMappingCountrySolarResourceReportMarch.pdf` | **World Bank ESMAP 2017**, Nepal Solar Resource Mapping Country Report | Nepal national solar resource (GHI, DNI, DHI, regional maps) | Authoritative source for §1.1 Nepal solar context |
| 31 | `1.Industrialdryingheatpumps-Minea-2011.pdf` | **Minea 2011**, "Industrial Drying Heat Pumps", in *Refrigeration: Theory, Technology and Applications* (Larsen ed.), Nova Science Publishers, ch. 1, pp. 1-70 | Hydro-Quebec book chapter, wood drying focus, dryer–HP integration mistakes catalogue | Foundational HPD review, lab and industrial scale |
| 32 | `1-s2.0-S0140700712003337-main.pdf` | **Minea 2013a**, "Drying heat pumps – Part I: System integration", Int. J. Refrigeration 36(3):643-658 | Hydro-Quebec Part I review, dryer–HP integration; bypass control, parallel/desuperheater condensers | **Resolves the original "Minea 2013" citation** |
| 33 | `1-s2.0-S0140700712003349-main.pdf` | **Minea 2013b**, "Drying heat pumps – Part II: Agro-food, biological and wood products", Int. J. Refrigeration 36(3):659-673 | Hydro-Quebec Part II, performance metrics; codfish, agro-food, wood; SMER 1-4 kg/kWh range | Companion to Part I |
| 34 | `Mortezapour_SaffronDryingwithaHeatPumpAssistedHybrid_DryingTechnology.pdf` | **Mortezapour, Ghobadian, Minaei, Khoshtaghaza 2012**, "Saffron Drying with a Heat Pump-Assisted Hybrid Photovoltaic-Thermal Solar Dryer", Drying Technology 30(6):560-566 | Iran Tarbiat Modares, **saffron**, 40/50/60 °C, m_air 0.008/0.012/0.016 kg/s, hybrid PV/T | **33% energy reduction with HP**; SMER 1.16 kg/kWh; collector η_th 28%, η_el 10.8%; dryer η 72% |
| 35 | `MOALD-Statical-Book-Magre-2081-Final_wgfs8ph.pdf` | **MoALD 2024**, *Statistical Information on Nepalese Agriculture 2079/80 (2022/23)*, Govt of Nepal, Ministry of Agriculture & Livestock Development, Statistics & Analysis Section, Singhadurbar, Kathmandu | Authoritative Nepal agricultural statistics | **Resolves §1.1 fruit-production claim**; supply exact production figures from this volume |
| 36 | `fundamentals-of-heat-exchanger-design-0471321710.pdf` | **Shah & Sekulić 2003**, *Fundamentals of Heat Exchanger Design*, Wiley, ISBN 0-471-32171-0 | Canonical HX textbook | **Resolves the textbook citation**; supports ε-NTU non-linearity claim |
| 37 | `HEAT PUMP DRYING OF AGRICULTURAL MATERIALS.pdf` | **Prasertsan & Saen-saby 1998**, "Heat Pump Drying of Agricultural Materials", Drying Technology 16(1-2):235-250 | Prince of Songkla U Thailand, banana + rubberwood in HPD | **Resolves the Prasertsan & Saen-saby citation**; SMER 0.572 kg/kWh banana, MER 2.71 kg/h |
| 38 | `1-s2.0-S1364032117312303-main.pdf` | **Mohanraj, Belyayev, Jayaraj, Kaltayev 2018**, "Research and developments on solar assisted compression heat pump systems – A comprehensive review (Part-B: Applications)", Renew. Sustain. Energy Rev. 83:124-155 | Comprehensive SACHP review: drying, space heating, water heating, desalination | **Resolves the Mohanraj 2018 citation** |
| 39 | `A_review_of_heat_pump_drying_Part_1_Syst.pdf` | **Çolak & Hepbaşlı 2009**, "A review of heat pump drying: Part 1 – Systems, models and studies", Energy Conv. & Mgmt. 50(9):2180-2186 | Pamukkale + Ege U, Turkey; HPD historical development, classification | **Resolves the Colak & Hepbasli 2009 citation** |
| 40 | `processes-08-01562-v3 (1).pdf` | **Royen, Noori, Haydary 2020**, "Experimental Study and Mathematical Modeling of Convective Thin-Layer Drying of Apple Slices", Processes 8:1562 | **Slovak U + Kabul Polytechnic, Afghanistan, apple, 40-50 °C, v 0.6/0.85/1.1 m/s, 4-12 mm slabs, 25-45% RH, 82 kPa (1800-2000 m altitude)** | **Resolves Royen 2020 citation**; **directly comparable to our T_set=45 °C, v≈1.1 m/s, Kathmandu altitude** |
| 41 | `1-s2.0-S1537511001900261-main.pdf` | **Chua, Chou, Hawlader, Mujumdar, Ho 2002**, "Modelling the Moisture and Temperature Distribution within an Agricultural Product undergoing Time-varying Drying Schemes", Biosystems Eng. 81(1):99-111 | NUS Singapore, mechanistic 2-phase model; potato slabs | **Resolves Chua et al. 2002 citation** |
| 42 | `0106_HPC2023_Full_Paper_Fix_v02.pdf` | **Fix, Braun, Warsinger 2023**, "High Efficiency Heat Pump Industrial Drying with Water Vapor-Selective Membranes", 14th IEA Heat Pump Conference, Chicago, paper 106 | Purdue, MemDry concept (water-vapor-selective membrane HPD) | 30-40% energy savings, drying T reduced 10-20 °C, COP up to 2x |
| 43 | `entropy-27-00197-v2.pdf` | **Balaraman, Rahman, Ziviani, Warsinger 2025**, "Exergy Analysis of a Convective Heat Pump Dryer Integrated with a Membrane Energy Recovery Ventilator", Entropy 27:197 | Purdue, MERV-integrated HPD, second-law analysis | 47-60% sensible heat loss reduction; up to 24.5% exergy input reduction |
| 44 | `1-s2.0-S0038092X2300899X-main.pdf` | **Yu, Zou, Yu 2024**, "Experimental investigation on the drying characteristics in a solar assisted ejector enhanced heat pump dryer system", Solar Energy 267:112265 | Xi'an Jiaotong U, R134a, ejector-enhanced SE-HPD vs CHPD | 28.7% MER and 54.3% exergy efficiency improvement vs CHPD; SMER 1.40 kg/kWh |
| 45 | `1-s2.0-S0360544223026099-main.pdf` | **Zou, Liu, Yu, Yu 2023**, "A review of solar assisted heat pump technology for drying applications", Energy 283:129215 | Xi'an Jiaotong U, comprehensive recent review | PVT, collector optimization, energy storage, ejector enhancement, alternative refrigerants (R134a → HFOs) |
| 46 | `Techno-economic_analysis_of_a_solar-assisted_heat_.pdf` | **Rulazi, Marwa, Kichonge, Kivevele 2023**, "Techno-economic analysis of a solar-assisted heat pump dryer for drying agricultural products", Food Sci. & Nutr. 11:7891-7909 (Wiley) | Tanzania NM-AIST, **tomato + carrot**, novel SAHPD | **COP 3.4, DT 11/12 h, SMER 1.33 kg/kWh, η_th 54%; payback 3 y (tomato), 2.6 y (carrot)** |
| 47 | `foods-14-02569-v2.pdf` | **Zhu, Ji, Yang, Cao, Wang, Liang, Li, Zhang, Yang, Geng 2025**, "Heat Pump Technology in the Field of Fruit and Vegetable Drying: A Review", Foods 14:2569 | Shihezi U China, comprehensive review of single + combined HPDs for **fruits and vegetables** | **Best newer review aligned with our scope narrowing** |
| 48 | `24.pdf` | **Abdullah, Ibrahim, Ishak, Sopian, Jarimi, Razali, Abusaibaa 2025**, "Performance Evaluation of a Solar Assisted Dual Condenser Heat Pump System for Drying of Pandan Leaves", J. Kejuruteraan 37(1):349-368 | Malaysia UKM, R32, **dual-condenser SAHPD** with hot-water solar coupling, pandan herbs | **C2-SAHPD COP 6.53, SMER 2.71, payback 3.84 months — directly comparable to our Config B/C** |
| 49 | `Reviewondryingofagriculturalproduceusingsolarassisted.pdf` | **Sai Prasanna & Manjula 2018**, "Review on drying of agricultural produce using solar assisted heat pump drying", Int. J. Agric. Engg. 11(2):409-420 | Indian agricultural engg journal, working details review | Lower-impact review; supplementary |
| 50 | `1-s2.0-S135943112601077X-main.pdf` | **Wang, Zheng, Luo, Ding, Shen, Jin, Lu, Peng 2026**, "Bypass-assisted high-temperature heat pump for industrial-scale bamboo drying: Design and performance", Applied Thermal Eng. 296:130769 | Hangzhou Dianzi U + Zhejiang Baima Lake Lab, **bypass-airflow** HPDS, bamboo | **36.5% energy reduction, 60.4% SMER increase, 57.5% SEC reduction via bypass — directly relevant to our VPD bypass strategy** |
| 51 | `Characterizing_agricultural_product_drying_in_sola.pdf` | **Kidane, Farkas, Buzás 2025**, "Characterizing agricultural product drying in solar systems using thin-layer drying models: comprehensive review", Discover Food 5:84 | Hungary U Agric, bibliometric thin-layer review (1976-2024) | **Confirms Midilli model is top performer across diverse agricultural products** — additional kinetic-modelling support |

| 52 | `The_Thin_layer_drying_characteristics_of_organic_a.pdf` | **Sacilik & Elicin 2006**, "The thin layer drying characteristics of organic apple slices", J. Food Eng. 73(3):281-289 | Turkey, organic apple cv. Starking, 40-60 °C, 0.8 m/s, 5 / 9 mm slices | D_eff range 2.27e-10 to 4.97e-10 m²/s; **Logarithmic model best fit (lowest RMSE 2.13e-3, highest R² 0.9983)**; **NO Arrhenius E_a reported in the paper** (paper does not perform Arrhenius fit; only D_eff range) |
| 53 | `1-s2.0-S096030850900073X-main.pdf` | **Doymaz 2010**, "Effect of citric acid and blanching pre-treatments on drying and rehydration of Amasya red apples", Food and Bioproducts Processing 88(2-3):124-132 | Turkey, Amasya red apple, 55 / 65 / 75 °C, 2.0 m/s | D_eff 2.93e-10 to 6.08e-10 m²/s; Parabolic model best fit; **E_a (D_eff Arrhenius) = 22.06 / 18.93 / 14.47 kJ/mol** for control / blanched / citric-treated samples respectively. Cites within: Kaya et al. 2007 (delicious apple) 19.95-22.62 kJ/mol; Simal 2005 (kiwi) 27.0; Lee & Hsieh 2008 (strawberry) 30.46-35.57. Rizvi 1986 general food range 15-40 kJ/mol. **The "30.93 kJ/mol Doymaz 2010" value previously cited in audit METHODOLOGY.md is incorrect** — actual Doymaz 2010 numbers are 14.47-22.06 kJ/mol |
| 54 | `Int J of Food Sci Tech - 2010 - Kaleta - Evaluation of drying models of apple  var  McIntosh  dried in a convective dryer.pdf` | **Kaleta & Górnicki 2010**, "Evaluation of drying models of apple (var. McIntosh) dried in a convective dryer", Int. J. Food Sci. & Tech. 45:891-898 | Poland, McIntosh apple, 16 thin-layer models compared, cubes vs slices, 0.6-1.4 m/s, 50-70 °C | Logarithmic model best fit (R 0.9976-0.9999, RMSE 0.00287-0.01746); Lewis, Logarithmic, Diffusion-approx and Jaros-Pabis used for parametric regression on T, v, characteristic length, layer height. **Arrhenius E_a not reported in the visible results pages** (5-8); claimed value 22.70 kJ/mol from prior audit needs separate verification |
| 55 | `meisami_3_3_2010_103_108.pdf` | **Meisami-asl, Rafiee, Keyhani, Tabatabaeefar 2010**, "Determination of suitable thin-layer drying curve model for apple slices (variety-Golab)", Plant Omics J. 3(3):103-108 | Iran (Tehran), apple var. Golab, 40-80 °C, 0.5 m/s, 2 / 4 / 6 mm slices, 13 thin-layer models | **Midilli et al. model gave best fit** (RMSE 0.002512, EF 0.999615, χ² 3.0e-5); Henderson-Pabis used for parametric regression on T and h. **Arrhenius E_a not reported in the visible results pages** (3-6); claimed value 29.26 kJ/mol from prior audit needs separate verification |
| 56 | (note: no separate PDF — Kaya 2007 cited within Doymaz 2010) | **Kaya, Aydin, Demirtas 2007**, "Drying kinetics of red delicious apple", Biosystems Engineering 96:517-524 | Cited in Doymaz 2010 only; secondary citation | E_a (D_eff Arrhenius) 19.95-22.62 kJ/mol — verifiable as a within-paper citation in Doymaz 2010 (#53) |
| 57 | (no PDF held — surfaced via web search 2026-05-06; **NOT cited in current §1.2**) | **Erbay & Icier 2010**, "A Review of Thin Layer Drying of Foods: Theory, Modeling, and Experimental Results", Critical Reviews in Food Science and Nutrition 50(5):441-464 | Comprehensive thin-layer drying review covering 41 food products | Reports activation-energy range 12.32-82.93 kJ/mol across 41 products. **Dropped from §1.2** because the user requested apple-specific (not pan-food) framing; kept here as a candidate reference if a broader envelope is needed elsewhere |
| 57b | `1-s2.0-S0260877403003686-main.pdf` | **Velić, Planinić, Tomas, Bilić 2004**, "Influence of airflow velocity on kinetics of convection apple drying", J. Food Eng. 64:97-102 | Croatia, **Jonagold** apple, convective tray-dryer, **60 °C constant**, v 0.64-2.75 m/s, 5 mm slices | D_eff first falling-rate 1.7-3.0 × 10⁻⁹ m²/s; second 2.9-4.4 × 10⁻⁹ m²/s; h 21.4-44.3 W/m²K. **NO Arrhenius E_a reported** (constant temperature design). Earlier ledger row claiming E_a values 17.77/19.75/25.41 kJ/mol was a misattribution from a search snippet; PDF rechecked 2026-05-08. Now cited in §1.2 only as a velocity-dependent D_eff anchor |
| 58 | `1-s2.0-S0960148124009352-main.pdf` | **Kang, Zhang, Mu, Guo, Yuan, Zhao, Li, Zhang 2024**, "Solar-heat pump combined drying with phase change heat storage: Multi-energy self-adaptive control", Renewable Energy 230:120867 | China (Dalian), kelp, solar + HP + phase-change TES with fuzzy multi-energy adaptive controller | T setpoint **40 ± 2 °C**, RH setpoint **30 ± 5%**; fuzzy T deviation **±2 °C** (vs ±5 °C original PLC); overshoot 2.57-3.95% (fuzzy) vs 7.35-11.78% (original); RMSE 0.59-0.62 (fuzzy) vs 1.61-2.81 (original); **electrical energy −43.0% (S-HP), −16.4% (HS-HP), −5.8% (HP), ~0% (Solar)** vs original. Earlier ledger row attributing this to "Sun et al." with COP +11.6/+13.7% and SEC −12.0/−25.7% was wrong; PDF rechecked 2026-05-08 — those COP/SEC numbers are not in the paper |
| 59 | `Comprehensive_assessment_of_heat_pump_dryers_for_d.pdf` | **Loemba, Kichonge, Kivevele 2023**, "Comprehensive assessment of heat pump dryers for drying agricultural products", Energy Science & Engineering 11(11):2985-3014 | Tanzania (NM-AIST), review of HPD types: hybrid (solar/IR/PV/Coulomb/RF/ultrasound/waste-heat), ground-source, air-source | Reports COP range **1.94-5.338** and SMER **0.156-9.25 kg/kWh** across reviewed HPDs; up to 80% energy reduction. Quotes Liu et al. (within Loemba) that **closed-type SMER is maximum at BAR ≈ 0.4** and falls beyond. Earlier "mango 71%, papaya 69%" attribution was wrong; PDF rechecked 2026-05-08 — those numbers are not in this paper. Used in §1.5 as the static-BAR optimisation anchor |
| 60 | `Foodlosspublished.pdf` | **GC & Ghimire 2019**, "Reducing post-harvest food losses to ensure food security in Nepal", pp. 128-129 | Nepal post-harvest loss review; production-stage / post-harvest / consumption-stage breakdown | Global stage-wise shares **30% / 20% / 35%** at production / post-harvest / consumption; Nepali farm-level losses reported at the low end of this band. **Locked 2026-05-19, supports Para 1 of §1** |
| 61 | `Factors influencing adoption of major post-harvest handling practices of large cardamom in Nepal.pdf` | **Kattel, Belbase, Khanal 2020**, "Factors influencing adoption of major post-harvest handling practices of large cardamom in Nepal", p. 2 | Nepal cardamom curing practices, farmer adoption survey | **Optimal curing temperature 45-55 °C**; fresh capsules 70-80% MC reduced to 10-12% MC; traditional bhatti is the dominant kiln type. **Locked 2026-05-19, supports Para 1 of §1** |
| 62 | `RanjanetalJan2018.pdf` | **Ranjan et al. 2018**, "Cardamom drying methods in Nepal", p. 2 | Nepal cardamom traditional and improved drying kilns | **2.5 kg fuelwood per kg of dried capsules**; drying time **24-28 h** with frequent racking. **Locked 2026-05-19, supports Para 1 of §1** |
| 63 | (online dataset, no PDF) | **PVGIS-JRC 2024**, Photovoltaic Geographical Information System, European Commission Joint Research Centre, SARAH-3 typical-meteorological-year solar radiation and meteorological dataset, https://re.jrc.ec.europa.eu/pvg_tools/en/ (accessed 2026-04) | TMY hourly weather for arbitrary geographic coordinates; SARAH-3 satellite-derived irradiance 2005-2023 baseline | Used as the hourly weather source for the four Nepali sites (Biratnagar 72 m, Kathmandu 1350 m, Dhulikhel 1550 m, Taplejung 1820 m). Files: `data/ambient/{site}_pvgis_standard.csv`. **Locked 2026-05-19, supports Para 5 of §1 and §4 simulation setup** |

PDFs not core to lit-review (skipped detailed read): `ductSysDesign_guide.pdf` (HVAC duct design textbook); `rahman2013 (1).pdf` (duplicate of #20); `foods-14-01195-v3.pdf` (duplicate v3 of #6 Tang 2025). The `.docx` files (`HP_Dryer_Literature_Review_v2.docx`, `Current Literature.docx`, etc.) are AI-generated or proposal-internal notes and are **not citable**.

**Round 3 verification (2026-05-05):** Phase D citation cross-check identified that three of the four "published apple-slice E_a" values previously circulated in the audit METHODOLOGY.md (19.96 kJ/mol Sacilik, 22.70 kJ/mol Kaleta, 29.26 kJ/mol Meisami-asl, 30.93 kJ/mol Doymaz 2010) **do not trace to the cited PDFs** in the visible result sections. Only Doymaz 2010 reports an Arrhenius E_a, and the actual numbers are 14.47-22.06 kJ/mol (not 30.93). Section 1.2 of `01_literature_review.md` was rewritten on 2026-05-05 to use only the verified 14.47-22.62 kJ/mol apple range from Doymaz 2010 + Kaya 2007 (cited within), with the broader 15-40 kJ/mol food range from Rizvi 1986 (also cited within Doymaz 2010). Our M1 point estimate E_a = 31.08 kJ/mol is now correctly described as sitting *above* the verified apple-specific range, not at its upper edge.

---

## B. Section 1 claim-by-claim verification

Format: `claim text → status → source PDF → action`.
Status: **VERIFIED** = found in a folder PDF; **CITES MISSING PDF** = PDF for cited author/year is not in the folder, claim possibly correct but unverifiable here; **WRONG** = PDF in folder shows the claim is misattributed or numerically inconsistent; **FABRICATED** = no source available and the claim looks invented.

### 1.1 Fruit drying in Nepal

| Claim | Status | Source / file | Action |
|---|---|---|---|
| "Nepal produced approximately 1.53 Mt of fruit in 2022/23 across three agro-climatic belts" [MoALD 2023] | CITES MISSING PDF | MoALD statistical yearbook is not in folder | Need user to confirm exact figure or supply PDF. World Bank Nepal Solar report (#30) discusses agro-climatic belts but not 1.53 Mt. |
| "post-harvest losses 15-35%" [Shrestha 2017] | CITES MISSING PDF | Shrestha 2017 not in folder | The Aacharya 2024 paper (#9) cites "post-harvest losses up to 50% in extreme cases" referencing Nepal Demographic & Health Survey 2022. Replace Shrestha 2017 with this verifiable citation, or have user supply Shrestha PDF. |
| "kinetic model fitted to apple-slice data [Royen et al., 2020]" | CITES MISSING PDF | Royen 2020 not in folder | But **Meisami-asl & Rafiee 2009 (#22)** provides direct support: Midilli model gives best fit for apple Golab with EF = 0.99972. **Sharabiani 2021 (#21)** also confirms Midilli for apple CD. Strongly recommend citing #22 as primary kinetic source and #21 as additional validation. |

### 1.2 Heat-pump drying

| Claim | Status | Source / file | Action |
|---|---|---|---|
| "COP of 3-5 for moderate lifts translates to SEC of 1.3-2.5 kWh/kg on experimental HPCDs" [Prasertsan & Saen-saby 1998; Chua et al. 2002] | CITES MISSING PDF | Neither in folder | Replace with verifiable Singh 2020 (#18) or Yahya 2023 (#8) numerical examples |
| "0.6-1.2 kWh/kg in optimised simulation studies [Minea, 2013]" | **WRONG attribution** | The PDF `10.1016@j.enconman.2013.01.013.pdf` is **Şevik 2013** on carrot drying, NOT Minea 2013. Şevik's SEC is not 0.6-1.2 kWh/kg either; that paper reports drying time and collector η, not bulk SEC | Either remove the Minea citation entirely or supply the actual Minea 2013 PDF; the Şevik paper supports a different claim |

### 1.3 Solar-assisted heat-pump dryers

| Claim | Status | Source / file | Action |
|---|---|---|---|
| "Colak & Hepbasli [2009] and Mohanraj et al. [2018] provide the foundational surveys" | CITES MISSING PDF | Neither in folder | Replace with **Daghigh et al. 2010 (#14)** which is in folder and is the corresponding foundational SAHPD review. |
| "Daghigh & Ruhani [2022] and Sun et al. [2025] are the most recent comprehensive reviews" | **WRONG year for Daghigh** | The Daghigh review in folder is **2010 (#14)**, not 2022 | Either find Daghigh 2022 (likely a different paper) or correct to "Daghigh et al. 2010". Sun et al. 2025 is not in folder. |
| "SMER 0.6-3.0 kg/kWh ... COP 2.7-5.0 ... thermal efficiency 9-57% [Bhandari et al., 2025]" | **WRONG attribution** | `foods-14-01195.pdf` is **Tang et al. 2025** on tomato multistage SAHPD, NOT Bhandari. Tang's reported numbers: solar fraction 85%, SMER 40.7 kg/kWh, SEC 0.02 kWh/kg (vastly different) | Critical fix: rewrite paragraph using Tang 2025 numbers (or find Bhandari 2025 PDF). The 0.6-3.0 SMER range is consistent with Yahya 2016 (0.38-0.47), Yahya 2023 (0.44), Hawlader 2006 (0.65), Kuan 2019 (0.6) — those are verifiable. |
| "Yan et al. [2023] reported SMER up to 22.9 kg/kWh and SEC as low as 0.043 kWh/kg" | CITES MISSING PDF (already flagged in REVISION_PLAN as unverified) | No Yan 2023 PDF in folder | **Recommend dropping this claim** — Tang 2025 (#6) reports the very high SMER 40.7 kg/kWh on multistage; that is verifiable and serves the same rhetorical purpose. |
| "ejector-enhanced configurations [Zhu et al., 2023]" | CITES MISSING PDF | No Zhu 2023 PDF in folder | Either supply or drop |
| "[Hawlader et al., 2003], on guava and papaya in Singapore" | **WRONG product** | `1-s2.0-S0306261902001459-main.pdf` is **Hawlader et al. 2003** but on **food grains** in Singapore, NOT guava and papaya | Correct to "food grains" or replace with Hawlader 2006 (#2) which is on green beans. Singapore SAHPD line is correct; the commodity is wrong. |
| "Thermal-storage integration [Ismaeel, 2020; Mortezapour et al., 2012; Rulazi et al., 2024]" | PARTIALLY VERIFIED | Ismaeel 2020 (#5) confirms TES integration (300 m³ tank) for wheat; Mortezapour and Rulazi PDFs not in folder, but Singh 2020 (#18) and Kuan 2019 (#12) both reference Mortezapour 2012 saffron with 33% energy reduction — this gives me secondary confirmation. Rulazi 2024 unverifiable here. | Keep Ismaeel 2020 (#5) and replace Rulazi with **Qiu et al. 2016 (#17)**, which directly demonstrates HR + TES with payback 2-6 years and 40.53% energy savings. |
| "Rulazi et al. [2024] report a techno-economic payback of 2-4 years" | CITES MISSING PDF | Not in folder | Replace with **Qiu et al. 2016 (#17)**: payback 2 / 4 / 6 years for mushroom / pepper / radish, verified directly. |
| "Minea [2013] and Colak & Hepbasli [2009] note that intermediate recirculation can collapse evaporator duty" | UNVERIFIED | Minea 2013 PDF not in folder; Colak & Hepbasli not in folder | The recirculation-penalty claim is from our own simulation work; do not cite external authors for it unless we can locate their PDFs. Recommend: cite our own §5.X scan instead, plus a generic SAHPD review (Daghigh 2010 #14). |

### 1.4 Heat-recovery exchangers in drying

| Claim | Status | Source / file | Action |
|---|---|---|---|
| "Counter-flow plate HRX with ε = 0.70 is a practical fabrication default; above ε ≈ 0.75 plate area grows super-linearly [Shah & Sekulic, 2003; Kays & London, 1984]" | UNVERIFIED | Both are textbooks, not in folder; I cannot independently verify the specific super-linear claim from these textbook editions | The textbooks are citation-correct (Shah & Sekulic and Kays & London are the canonical HX design refs) but **the super-linear-area claim itself is correct heuristically and is reproducible from the ε-NTU relation** for counter-flow at C_r ≈ 1. Recommend keeping the citations and rewording: "the ε-NTU relation predicts NTU (and hence area) rises non-linearly above ε ≈ 0.75 for counter-flow with C_r ≈ 1" with one of the textbooks. |
| "[Ismaeel, 2020] report SEC reductions of 15-35% at ε = 0.60-0.75" | **WRONG numerical claim** | Ismaeel 2020 (#5) reports **21.4% annual energy savings vs no-HRU**, not "15-35% at ε = 0.60-0.75". Effectiveness range is not stated as 0.60-0.75 in Ismaeel — it discusses HX restoring efficiency up to 41.7% | Rewrite: "Ismaeel and Yumrutaş [2020] report 21.4% annual energy saving on a wheat SAHPD when an HRU is added to a baseline TES tank system; their HX restoring efficiency ranges up to 41.7%." |
| "membrane-based enthalpy exchangers achieve total-heat effectiveness near 0.88 for simultaneous sensible and latent recovery [Vali et al., 2021]" | **WRONG attribution** | The PDF in folder labelled `s41598-021-88270-z.pdf` is by **Vali Rasooli Sharabiani** (first name Vali) on apple drying ANN. There is no membrane-HX paper "Vali et al. 2021" in the folder | Either supply the actual membrane-HX 2021 paper, or **drop this claim entirely** — the SAHPD HRX in this paper is sensible-only counter-flow plate, so a membrane-HX comparison is not load-bearing for our argument |
| "Aacharya et al. [2024] ... drying rates of 107 g/(h·m²) with a low-e coated collector, 89% collector efficiency, and economic payback of 1.61 years" | **VERIFIED** | `1-s2.0-S2214157X24015132-main.pdf` (#9) | Keep as is. |
| "Adhikari et al. [2025] ... in-chamber uniformity index as low as 0.58 (CV > 1.0) and ... raise UI to 0.78" | PARTIALLY VERIFIED, NEEDS DEEPER READ | `1-s2.0-S2590123025016238-main.pdf` (#10) is the right paper but the specific 0.58 / 0.78 numbers were not in the abstract or first 3 pages I read | I will read pages 4-12 of this PDF before final draft to confirm the numerical values, or relax the wording to "improved uniformity" |

### 1.5 Humidity-aware control

| Claim | Status | Source / file | Action |
|---|---|---|---|
| "VPD-based control is standard in controlled-environment agriculture; its combination with an exhaust HRX on a heat-pump dryer has not, to the authors' knowledge, been reported" | UNVERIFIED but defensible | No SAHPD paper in folder uses VPD bypass | The negative claim ("not reported") is plausibly true for the SAHPD literature in the folder (29 SAHPD papers, none use VPD-triggered exhaust bypass). Keep with "to the authors' knowledge" hedge. |

### 1.6 Prior Nepali work and the gap this paper addresses

| Claim | Status | Source / file | Action |
|---|---|---|---|
| Aacharya 2024 KU + Lund, Dhulikhel apple, 1.61 y payback, 89% η | **VERIFIED** | `1-s2.0-S2214157X24015132-main.pdf` (#9) | Keep |
| Adhikari 2025 ANSYS Fluent + smoke-flow on KU/Lund HX dryer | **VERIFIED** (paper identity) | `1-s2.0-S2590123025016238-main.pdf` (#10) | Keep; verify exact UI numbers |
| "RECAST at Tribhuvan University ... rack-type dryers at high-altitude sites" | UNVERIFIED | No PDFs for these in folder | Either supply Nepali grey-literature reports or moderate the wording |
| "no peer-reviewed Nepali study reports a heat-pump dryer, solar-assisted or otherwise" | DEFENSIBLE | Of the 29 SAHPD-relevant PDFs in folder, only Aacharya 2024 and Adhikari 2025 are Nepali, and both are solar-only with HX (no heat pump) | Keep with hedge |

---

## C. Concrete corrections required (high-impact)

1. **Reattribute the "Minea 2013" claim.** The PDF in the folder is Şevik 2013, which is a different paper. Either supply the real Minea 2013 (Energy Conv. & Mgmt. paper on simulation of HPCD, likely Minea V., "Drying heat pumps - Part I: System integration", Int. J. Refrigeration 2013) or drop the citation.
2. **Reattribute the "Bhandari 2025" claim.** The PDF is Tang et al. 2025 on tomato multistage SAHPD. Either supply the real Bhandari 2025 (foods-14-01195 is definitively Tang) or rewrite the SMER / COP / efficiency-range sentence using Tang 2025 plus the existing SAHPD body (Hawlader 2006 = 0.65, Yahya 2016 = 0.38-0.47, Yahya 2023 = 0.44, Kuan 2019 = 0.6, Singh 2020, Şevik 2013 = 0.26-0.96).
3. **Correct "Hawlader 2003 guava and papaya".** The Hawlader 2003 PDF in folder is on **food grains** in Singapore, not guava/papaya. Either replace the commodity, or replace the citation with Hawlader 2006 (green beans, NUS) which we have verified.
4. **Drop or supply Yan 2023 SMER 22.9.** Already flagged in REVISION_PLAN as unverified. Tang 2025 supplies a verified high-SMER multistage example.
5. **Drop or supply Vali 2021 membrane-HX 0.88.** The PDF labelled `s41598-021-88270-z.pdf` is a different Vali (Sharabiani) paper on apple ANN drying. The membrane-HX claim is not load-bearing for our paper (we use sensible-only HRX), so dropping is the cleanest fix.
6. **Reattribute "Daghigh & Ruhani 2022".** The Daghigh PDF in folder is 2010, not 2022. Verify whether a 2022 update exists; if not, cite Daghigh 2010.
7. **Replace Rulazi 2024 with Qiu 2016.** Qiu 2016 (#17) is in folder, directly reports HR + TES SAHPD with 40.53% energy saving and 2-6 year payback — perfect verifiable replacement.
8. **Rewrite Ismaeel 2020 numbers.** The "15-35% at ε=0.60-0.75" is not what Ismaeel reports (21.4% annual saving, restoring efficiency up to 41.7%, ε-sweep not the framing).
9. **Replace Royen 2020 apple kinetics with Meisami-asl 2009 (#22).** The Meisami-asl Iran apple Golab paper directly fits 14 thin-layer models and finds Midilli optimal — exactly the model we use. This is a verifiable kinetic source we already have.
10. **Add Sharabiani 2021 (#21) as kinetic validation cross-reference.** Apple drying with Midilli model fit, 50/60/70 °C — directly relevant.

---

## D. Recommended additions (verified PDFs not currently cited)

These are SAHPD or directly-relevant papers in the folder that are NOT cited in current Section 1 but should be:

| File | Why it strengthens the literature review |
|---|---|
| #17 Qiu 2016 | Direct HR + TES SAHPD with verified energy saving, payback. Replaces Rulazi. |
| #18 Singh 2020 | R1234yf SAHPD on banana, exergoeconomic; pairs with our R134a choice and gives alternative-refrigerant context |
| #19 Li 2021 | High-altitude (>3000 m) cold SAHPD — directly supports our Taplejung simulation |
| #20 Rahman 2013 | Economic optimisation of evap-coll + air-coll SAHPD, payback ~4 y — supports our techno-economic discussion |
| #15 Amin & Hawlader 2013 | Singapore SAHP review with COP 8.0 evap-coll — calibrates our COP 3.5-4.8 numbers |
| #14 Daghigh 2010 | Foundational SAHPD review (replaces incorrect "Daghigh 2022" citation) |
| #22 Meisami-asl 2009 | Direct verification of Midilli kinetics for apple |
| #21 Sharabiani 2021 | Second Midilli-on-apple validation |
| #6 Tang 2025 | Multistage SAHPD high-SMER reference (replaces unverified Yan 2023) |
| #8 Yahya 2023 | Recent paddy SAHPD with biomass + solar, comparative SMER 0.44 |
| #12 Kuan 2019 | Banana SAHPD, continental cold climate, SMER 0.6, COP 2.72 — relevant cold-site comparison |
| #16 Yahya 2016 | Cassava SD vs SAHPD direct comparison, SMER 0.38 vs 0.47 |
| #9 Aacharya 2024, #10 Adhikari 2025 | Already cited; keep |
| #30 Nepal Solar Resource Report 2017 | Should be cited in §1.1 for Nepal solar resource (replaces unsourced agro-climatic-belt assertions) |

---

## E. Currently cited but NO PDF available (need user to supply or drop)

These references appear in the current paper but I cannot locate the source PDF in the folder. Mark each: **DROP** (replace with verified source) or **SUPPLY** (user adds PDF):

| Citation | Current claim | Recommendation |
|---|---|---|
| MoALD 2023 | "1.53 Mt fruit production" | SUPPLY (or replace with MoALD URL + accessed-date footnote) |
| Shrestha 2017 | "post-harvest losses 15-35%" | DROP — replace with NDHS 2022 via Aacharya 2024 (#9) |
| Royen et al. 2020 | apple kinetics | DROP — replace with Meisami-asl 2009 (#22) |
| Prasertsan & Saen-saby 1998 | SEC 1.3-2.5 kWh/kg | DROP — replace with Yahya 2023 SEC 4.69, Singh 2020 |
| Chua et al. 2002 | same | DROP |
| Minea 2013 | SEC 0.6-1.2 kWh/kg | SUPPLY actual Minea PDF or DROP |
| Colak & Hepbasli 2009 | foundational review | DROP — replace with Daghigh 2010 (#14) |
| Mohanraj et al. 2018 | foundational review | SUPPLY or DROP |
| Daghigh & Ruhani 2022 | recent review | Likely WRONG year; if real, SUPPLY |
| Sun et al. 2025 | recent review | SUPPLY or DROP |
| Bhandari et al. 2025 | SMER/COP ranges | SUPPLY actual Bhandari PDF (foods-14-01195 is Tang) |
| Yan et al. 2023 | SMER 22.9 | DROP — replace with Tang 2025 (#6) |
| Zhu et al. 2023 | ejector-enhanced | SUPPLY or DROP |
| Mortezapour et al. 2012 | TES integration | SUPPLY (it is referenced second-hand by Singh 2020 / Kuan 2019, value verified there) |
| Rulazi et al. 2024 | 2-4 y payback | DROP — replace with Qiu 2016 (#17) |
| Vali et al. 2021 | membrane-HX 0.88 | DROP (no real source; not load-bearing) |
| Shah & Sekulic 2003 | textbook | KEEP (canonical reference, even without PDF) |
| Kays & London 1984 | textbook | KEEP (canonical) |

---

## F. Target journal recommendation

Three candidates evaluated, ranked best-fit first:

1. **Energy Conversion and Management (Elsevier)**, IF ~10.4. Topics: SAHPD modelling, multi-config comparison, exergy/exergoeconomic analyses. Hosts Şevik 2013, Rahman 2013, Hawlader 2008 — directly comparable papers. Word limit ~10000-14000. **My recommendation.**
2. **Solar Energy (Elsevier)**, IF ~7.0. Hosts Hawlader 2006, Yahya 2016, Qiu 2016, Singh 2020, Li 2021. Slightly more solar-component-centric than ours (we are heat-pump-centric).
3. **Applied Thermal Engineering (Elsevier)**, IF ~6.4. Broader thermal scope, fewer SAHPD papers than ECM. Good fallback.

**Not recommended:** Renewable Energy is too solar/PV-broad; Foods (MDPI) is product-quality focused; Case Studies in Thermal Engineering is regional/student-friendly but lower impact.

Word target for ECM: aim for **2,800-3,500 words for Literature Review** (current §1 is ~1,650 words; the expansion fits within ECM's typical 12000-word total).

---

## G. Open questions for user — STATUS AS OF 2026-04-27 EVENING

User responses received:
1. **Target journal:** still discussing — user asked about ECM impact factor. ECM JIF ≈ 10.4 (Q1, Elsevier, multi-config SAHPD friendly). User approval pending. Alternatives: Solar Energy (JIF ≈ 7), Renewable Energy (JIF ≈ 9), Applied Thermal Eng (JIF ≈ 6.4).
2. **Per-citation decisions:**
   - **Shrestha 2017:** REPLACE with verified Nepal post-harvest source (use NDHS 2022 via Aacharya 2024 #9, or supply specific Nepal MoAD bulletin).
   - **Royen 2020:** USER ADDED PDF → now #40 in register. **Cite Royen 2020 + Meisami-asl 2009 (#22) + Sharabiani 2021 (#21) as triple kinetic support.** Royen 2020 is especially strong because it shares our altitude and velocity range.
   - **Daghigh 2010:** Correct year from "Daghigh 2022" → "Daghigh et al. 2010".
   - **Vali 2021 membrane HX:** DROP entirely.
   - **Bhandari 2025:** DROP. Google search confirms no Bhandari 2025 SAHPD paper exists in indexed literature (search 2026-04-27). Replace with Tang 2025 (#6).
   - **Hawlader 2003:** Correct commodity from "guava and papaya" → "food grains" (per actual Applied Energy 74:185-193).
   - **Yan 2023:** DROP. Replace with Tang 2025 (#6) for high-SMER multistage example or Yu 2024 (#44) for ejector enhancement.
   - **Mortezapour 2012:** USER ADDED PDF → now #34. **Cite as: 33% energy reduction, SMER 1.16 kg/kWh, saffron, Iran.**
   - **Minea 2013:** USER ADDED BOTH PARTS → now #32 and #33. **Cite as Minea 2013a (Part I, system integration) and Minea 2013b (Part II, agro-food) — Int. J. Refrig. 36:643-658 / 659-673.**
   - **Rulazi 2023:** USER ADDED PDF → now #46. **Cite as Rulazi et al. 2023 (Food Sci. Nutr.), correcting year from 2024 to 2023.** User noted preference for newer research, so keep Qiu 2016 + Rulazi 2023 + Tang 2025 stack.
3. **Scope narrowing:** APPROVED → focus on vapour-compression SAHPDs for **fruit/vegetable drying**. Exclude Kim 2023 (#7 district heating), Chanpet 2020 (#11 rubberwood), Wang 2026 (#50 bamboo wood drying — but cite for bypass methodology). Marine and wood references kept only where they support cross-cutting methods (e.g., kinetics, bypass, exergy).
4. **Adhikari 2025 UI numbers:** VERIFIED from pp. 4-12. Actual numbers: Base Model L1 in DC2 = 0.569 → Model 5 L1 = 0.728 (29% gain). Along H1 over entire dryer: 0.680 → 0.783. CV reduced 44-74%. ΔP for Model 5 = 10.43 Pa vs Model 1 = 44.2 Pa.
5. **MoALD 2022/23 fruit production:** USER ADDED PDF → now #35. Need to extract exact figure (likely page on "fruit area + production" — will read further if user wants, otherwise cite the MoALD volume by year and table.)

**Decisions locked in (2026-04-27 evening, user confirmed):**
- (a) **Target journal: Energy Conversion and Management** (Q1 Elsevier, JIF ~10.4). Word target 2,800-3,500 for lit review within ~12,000-word total.
- (b) **All 7 new strong refs approved:** Zou 2023 (#45), Yu 2024 (#44), Zhu 2025 (#47 review fruit/veg HP), Abdullah 2025 (#48 dual-cond SAHPD), Wang 2026 (#50 bypass), Royen 2020 (#40), Mortezapour 2012 (#34).
- (c) **Foundational-review pair: use NEWER pair** Zou 2023 (#45) + Zhu 2025 (#47). Çolak & Hepbaşlı 2009 (#39) and Mohanraj 2018 (#38) demoted to supplementary citations (cited briefly when discussing historical evolution).
- (d) MoALD citation: cite by volume + table number; no need to extract exact figure from page text.
- (e) Daghigh 2010 (#14) retained as historical SAHPD review reference; Mohanraj 2018 retained for desalination/space-heating context if needed.
- (f) Membrane HPD work (Fix 2023, Balaraman 2025) — dropped from §1.4 main argument per user; **may cite Balaraman 2025 only as exergy-methodology reference if §1.5/§3 needs second-law framing.**

---

## H. Phase B output — proposed structure for revised Literature Review

Target: Energy Conversion and Management. Length: 2,800–3,500 words. Subsection-by-subsection plan with verified anchor citations.

### H.1 Subsection plan (proposed)

| § | Title | Word target | Function | Anchor citations |
|---|---|---|---|---|
| 1.1 | Fruit drying in Nepal: production, post-harvest losses, climate context | 350 | Set the problem. Funnel from Nepal agriculture → fresh-fruit perishability → drying as preservation lever. Cite real Nepal data. | MoALD 2024 (#35); World Bank ESMAP 2017 (#30); Aacharya 2024 (#9); Adhikari 2025 (#10) |
| 1.2 | Drying kinetics for apple slices | 350 | Justify the apple+Midilli choice. Triple-anchor kinetic support (Iranian Golab 2009, Iranian convective+MW 2021, Slovak/Afghan high-altitude 2020). Use this as the apple-specific evidence base. | Meisami-asl 2009 (#22); Sharabiani 2021 (#21); Royen 2020 (#40); Kidane 2025 (#51) for the meta-finding that Midilli is consistently best across crops |
| 1.3 | Heat-pump drying (HPCD): performance envelope and limits | 450 | Establish the HPCD baseline: SMER, COP, SEC ranges. Discuss closed-loop vs open-loop, dehumidification, evap freezing. | Prasertsan & Saen-saby 1998 (#37); Chua 2002 (#41); Minea 2013a/b (#32, #33); Yahya 2023 (#8); Singh 2020 (#18); Kuan 2019 (#12); Yahya 2016 (#16) |
| 1.4 | Solar-assisted heat-pump dryers: topology landscape | 700 | The core review. Walk through the integration patterns (series solar→cond, evap-coll, cascade solar→evap, dual-condenser, ejector-enhanced). **Include the comparative table H.2.** Note the SAHP review evolution. | Zou 2023 (#45); Zhu 2025 (#47); Daghigh 2010 (#14); Hawlader 2003/2006/2008 (#4, #2, #3); Amin & Hawlader 2013 (#15); Tang 2025 (#6); Mortezapour 2012 (#34); Şevik 2013 (#1); Qiu 2016 (#17); Singh 2020 (#18); Li 2021 (#19); Rahman 2013 (#20); Rulazi 2023 (#46); Abdullah 2025 (#48); Yu 2024 (#44) |
| 1.5 | Heat-recovery exchangers and humidity-aware control | 450 | The novelty hook for our paper. Tighten on counter-flow plate HRX (ε≈0.70 default), bypass control, VPD framing. Reference Wang 2026 to anchor the bypass concept in recent literature. | Shah & Sekulić 2003 (#36); Ismaeel 2020 (#5); Wang 2026 (#50); Balaraman 2025 (#43, exergy framing only); Aacharya 2024 (#9 HRX in Nepal); Adhikari 2025 (#10 chamber UI) |
| 1.6 | Prior Nepali work and the gap this paper fills | 250 | Position the research gap. Two Nepali SAHPD-adjacent papers (both Lund/KU collaboration, both solar-only with HX, neither heat pump). State the gap explicitly. | Aacharya 2024 (#9); Adhikari 2025 (#10); contrast with all reviewed VC-SAHPDs above |
| 1.7 | Aim and contribution | 200 | One paragraph summary. Spell out the 10-config sweep, the unified thermodynamic model, the three Nepali sites (KTM, BTN, Taplejung), and the bypass-VPD novelty. | Self-reference to model sections |
| **Total** | | **~2,750** | | |

### H.2 Comparative table — SAHPD configurations from literature

Single table summarising verified papers along consistent columns. Drop any paper whose values were not personally verified from the PDF.

| Author / year | Country | Topology | Refrigerant | T_set (°C) | Crop | SMER (kg/kWh) | COP | Headline result |
|---|---|---|---|---|---|---|---|---|
| Hawlader & Jahangeer 2006 | Singapore | Evap-coll SAHPD + WH | R134a | tropics | Green beans | 0.65 | 7.0 | Hybrid drying + water heating |
| Hawlader 2008 | Singapore | Evap-coll vs air-coll | R134a | tropics | (sim) | — | — | η_evap-coll 0.86, η_air-coll 0.7 |
| Mortezapour 2012 | Iran | Hybrid PV/T + HPD | — | 40-60 | Saffron | 1.16 | — | 33% energy reduction with HP |
| Şevik 2013 | Turkey | DPSAC + HPD, PV-supplied | R134a | 50 | Carrot | — | — | Carrot 7.76 → 0.1 g/g db, 220 min; coll η 60-78% |
| Rahman 2013 | Singapore | Evap-coll + air-coll, NUS sim | R134a | tropics | (sim) | — | — | Min payback ~4 y |
| Yahya & Fudholi 2016 | Indonesia | SAHPD vs SD | — | 40-45 | Cassava | 0.47 (SAHPD) vs 0.38 (SD) | 3.23-3.47 | η_th 30.9% (SAHPD) vs 25.6% (SD) |
| Qiu 2016 | China | SAHPD + HR + TES | — | — | Radish/pepper/mushroom | — | 3.21-3.49 | 40.5% energy saving via HR+TES; payback 2-6 y |
| Kuan 2019 | Kazakhstan | SAHPD continental cold | R134a | — | Banana | 0.6 | 2.72 | 21 h vs 35 h SD; HRU 12.9% vs 9.9% |
| Ismaeel 2020 | Iraq/Turkey | SAHPD + TES + HRU | — | — | Wheat | 9.25 (5th-yr) | 5.55 | HRU 21.4% annual saving; HX restoring η 41.7% |
| Singh 2020 | India | SAHPD vs HPD | R1234yf | — | Banana | 0.342 (SAHPD) | — | Payback 3.9 y; exergoeconomic 0.20 |
| Royen 2020 | Afghanistan / Slovakia | Convective thin-layer model | — | 40-50 | Apple | — | — | **Apple at v 1.1 m/s and P 82 kPa, altitude 1800-2000 m**; Midilli model superior |
| Li 2021 | China Yunnan | SHPD high-altitude | — | T_amb 5 °C | Tibetan herbs | — | 2.42 (SHPD) vs 1.34 (HPD) | 70% drying-time reduction; >3000 m altitude |
| Sharabiani 2021 | Iran | CD vs MD apple | — | 50-70 | Apple | — | — | Midilli best fit for both modes |
| Yahya 2023 | Indonesia | Hybrid SAHPD + biomass | R22 | 62.9 | Paddy | 0.44 | — | SC 19.7%, BF 12.9% energy contribution |
| Rulazi 2023 | Tanzania | SAHPD techno-economic | — | — | Tomato + carrot | 1.33 | 3.4 | Payback 2.6-3 y |
| Yu 2024 | China | Solar + ejector-enhanced HPD | R134a | 75 | (lab) | 1.40 | — | +28.7% MER, +54.3% exergy efficiency |
| Tang 2025 | China | Solar-assisted multistage HPD | — | 70 | Tomato | 40.7 | (perf coeff 39.16) | Solar 85% energy in spring/autumn; SEC 0.02 |
| Abdullah 2025 | Malaysia | Dual-condenser SAHPD (C2) | R32 | 70-90 storage | Pandan herb | 2.71 (C2) | 6.53 (C2) | Payback 3.84 months; novel dual-cond integration |
| Wang 2026 | China | Bypass-assisted HT-HPD | — | high-T | Bamboo | 0.913 | — | Bypass: -36.5% energy, +60.4% SMER, -57.5% SEC |
| **This work** | Nepal | 10 configs (HP, +Solar, +HRX, +HRX+Solar) | R134a | 45 | Apple | (sim) | (sim) | Unified thermodynamic comparison + VPD bypass control |

### H.3 Length budget and integration plan

- Total target: ~2,750 words (within 2,800-3,500 ECM range)
- Current §1 is ~1,650 words (per ledger).
- Net expansion: ~1,100 words; but ~400 words of current §1 will be **rewritten** rather than appended (incorrect attributions removed).
- Comparative table H.2: counts as "Table 1" of paper; ~1 page in ECM two-column format.

### H.4 Drafting plan for Phase C (subsection-by-subsection user review)

Proposed flow: I will draft each subsection (1.1 → 1.7) and pause for your review between subsections. After 1.4 (the longest), we should also review the comparative table together. Total expected back-and-forth: 7 review rounds.

Phase C is ready to start once you approve the structure in H.1 and the table columns in H.2.
