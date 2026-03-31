# ========================================================
        # MODUL 2: AUTO-PILOT NORMAL (Evadare obstacole)
        # ========================================================
        if AUTO_MODE:
            env_data = env_sensors.get_data()
            dist = env_data.get("distance_cm", 999)
            
            # OPTIMIZARE: Procesăm scorul camerei AI DOAR aici, când suntem în modul care are nevoie de el
            stanga, centru, dreapta = get_ai_scores()
            
            # STAREA DE URGENȚĂ (Reflex Ultrasonic)
            if 2 < dist < 15:
                print("[FSM] Reflex Ultrasonic: OBSTACOL CRITIC! Evadare...")
                motor.set_left(-VITEZA_FATA)
                motor.set_right(-VITEZA_FATA)
                time.sleep(0.8) 
                motor.set_left(VITEZA_VIRAJ) 
                motor.set_right(-VITEZA_VIRAJ)
                time.sleep(0.75)
                motor.stop()
                time.sleep(0.75) 
                continue 

            # STAREA DE ANALIZĂ ȘI VIRAJ (Scor Cameră AI)
            elif centru > PRAG_PERICOL_AI:
                print(f"[FSM] Obstacol Video ({centru:.0f}). PUNEM FRÂNĂ...")
                motor.stop()
                time.sleep(0.75) 
                
                # Citim din nou camera să vedem situația actualizată după oprire
                stanga_clar, _, dreapta_clar = get_ai_scores()
                
                if stanga_clar < dreapta_clar:
                    print("[FSM] Viraj STÂNGA <-")
                    motor.set_left(-VITEZA_VIRAJ)
                    motor.set_right(VITEZA_VIRAJ)
                else:
                    print("[FSM] Viraj DREAPTA ->")
                    motor.set_left(VITEZA_VIRAJ)
                    motor.set_right(-VITEZA_VIRAJ)
                
                time.sleep(0.75) 
                motor.stop()
                time.sleep(0.75) 
                
            # STAREA DE NAVIGARE LINIȘTITĂ
            else:
                motor.set_left(VITEZA_FATA)
                motor.set_right(VITEZA_FATA)
                
            time.sleep(0.1)