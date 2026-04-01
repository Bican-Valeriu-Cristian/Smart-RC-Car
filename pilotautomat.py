 ========================================================
        # MODUL 2: AUTO-PILOT NORMAL (Explorare + Interceptare ArUco)
        # ========================================================
        if AUTO_MODE:
            env_data = env_sensors.get_data()
            dist = env_data.get("distance_cm", 999)
            
            stanga, centru, dreapta = get_ai_scores()
            pozitie_x = get_aruco_position(target_id=6)
            
            # --- STAREA 1: VEDE MARKERUL (Prioritate maximă: Aliniere și Oprire) ---
            if pozitie_x is not None:
                if dist <= 25:
                    print(f"[FSM] GATA! Am ajuns în fața codului la {dist:.1f}cm.")
                    motor.stop()
                    AUTO_MODE = False  # Pune pauză totală
                else:
                    # Virează spre cod în timp ce merge în față
                    K_VIRAJ = 40 # Cât de agresiv ia de volan (poți regla)
                    corectie = int(pozitie_x * K_VIRAJ)
                    
                    # Permitem motoarelor să urce până la 100% ca să poată lua curba eficient
                    m_stanga = clamp(VITEZA_FATA + corectie, 0, 100)
                    m_dreapta = clamp(VITEZA_FATA - corectie, 0, 100)
                    
                    motor.set_left(m_stanga)
                    motor.set_right(m_dreapta)
                    print(f"[FSM] Mă duc spre cod! Viraj: {corectie}")
                    
                time.sleep(0.1)
                continue # Sare peste detectarea de pereți ca să se concentreze doar pe marker

            # --- STAREA 2: EVITARE URGENȚĂ (Zid la sub 15cm) ---
            if 2 < dist < 15:
                print("[FSM] Zid fizic! Dau cu spatele...")
                motor.set_left(-VITEZA_FATA)
                motor.set_right(-VITEZA_FATA)
                time.sleep(0.8) 
                motor.set_left(VITEZA_VIRAJ) 
                motor.set_right(-VITEZA_VIRAJ)
                time.sleep(0.75)
                motor.stop()
                continue 

            # --- STAREA 3: OCOLIRE OBSTACOLE CU MIDAS (AI) ---
            elif centru > PRAG_PERICOL_AI:
                print("[FSM] Obstacol văzut de AI. Ocolesc...")
                motor.stop()
                time.sleep(0.5) 
                
                stanga_clar, _, dreapta_clar = get_ai_scores()
                if stanga_clar < dreapta_clar:
                    motor.set_left(-VITEZA_VIRAJ)
                    motor.set_right(VITEZA_VIRAJ)
                else:
                    motor.set_left(VITEZA_VIRAJ)
                    motor.set_right(-VITEZA_VIRAJ)
                
                time.sleep(0.75) 
                motor.stop()
                
            # --- STAREA 4: PLIMBARE LIBERĂ (Nu vede nici cod, nici zid) ---
            else:
                motor.set_left(VITEZA_FATA)
                motor.set_right(VITEZA_FATA)
                
            time.sleep(0.1)