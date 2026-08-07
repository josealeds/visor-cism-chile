import streamlit as st
import pandas as pd
import json
import requests
import time
import re

st.set_page_config(page_title="CISM - Resultados en Vivo", layout="wide", initial_sidebar_state="collapsed")

# REEMPLAZA con la misma URL que usaste en app.py
DB_URL = "https://torneo-cism-default-rtdb.firebaseio.com/torneo_db.json"

def cargar_db():
    try:
        respuesta = requests.get(DB_URL)
        if respuesta.status_code == 200 and respuesta.json() is not None:
            return respuesta.json()
        return {}
    except:
        return {}

# Ocultar menús y ajustar márgenes, preparando el espacio exacto para el pie de página
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    .footer-text {text-align: center; color: #7f8c8d; font-size: 14px; margin-top: 40px; padding-top: 10px; border-top: 1px solid #bdc3c7;}
    </style>
""", unsafe_allow_html=True)

db = cargar_db()

if not db or not db.get("Esgrimistas"):
    st.title("Esperando inicio de la competencia...")
    time.sleep(10)
    st.rerun()

config = db.get("Configuracion_Torneo", [{}])[0] if db.get("Configuracion_Torneo") else {}
nombre_t = config.get("nombre_torneo", "Torneo Interescuelas Matrices CISM")
fecha_t = config.get("fecha_torneo", "")
texto_fecha = f" - {fecha_t}" if fecha_t else ""

# Título global inamovible
st.title(f"🏆 {nombre_t} - Pizarra Oficial{texto_fecha}")
st.write("---")

estados = db.get("Estado_Categorias", {})
computo_masc = db.get("Computo_Masc", {})
computo_fem = db.get("Computo_Fem", {})

# Detectar categorías inscritas
categorias_activas = sorted(list(set(f"{e['arma']}_{e['genero']}" for e in db.get("Esgrimistas", []))))

todas_finalizadas = False
if categorias_activas:
    todas_finalizadas = all(estados.get(cat) == "FINALIZADA" for cat in categorias_activas)

# --- MODO CARRUSEL PARA TV ---
if "tv_index" not in st.session_state:
    st.session_state.tv_index = 0
    
# El carrusel elimina la Info de Control. Solo rota entre armas.
carrusel = list(categorias_activas)

# Si todo terminó, agregamos la diapositiva del Cómputo General al final del bucle
if todas_finalizadas and len(categorias_activas) > 0:
    carrusel.append("COMPUTO_GENERAL")

if not carrusel:
    st.info("Procesando datos del torneo...")
    st.markdown("<div class='footer-text'>Sistema de Gestión CISM Chile v4.6, diseñado por el maestro José De Sousa</div>", unsafe_allow_html=True)
    time.sleep(10)
    st.rerun()
    
# Extraer la diapositiva que corresponde a este ciclo
diapositiva_actual = carrusel[st.session_state.tv_index % len(carrusel)]

if diapositiva_actual == "COMPUTO_GENERAL":
    st.header("🏆 CÓMPUTO GENERAL DEFINITIVO (COPA)")
    
    df_m = pd.DataFrame(computo_masc).T
    df_f = pd.DataFrame(computo_fem).T
    
    col_c1, col_c2 = st.columns(2)
    
    if not df_m.empty and not df_f.empty:
        with col_c1:
            st.subheader("MASCULINO")
            st.dataframe(df_m, use_container_width=True)
        with col_c2:
            st.subheader("FEMENINO")
            st.dataframe(df_f, use_container_width=True)
            
        st.write("---")
        st.subheader("🏅 GRAN TOTAL POR INSTITUCIÓN")
        df_totales = pd.DataFrame([df_m.sum(), df_f.sum()], index=["TOTAL MASCULINO", "TOTAL FEMENINO"])
        df_totales.loc["GRAN TOTAL (COPA)"] = df_totales.sum()
        df_totales = df_totales.sort_values(by="GRAN TOTAL (COPA)", axis=1, ascending=False)
        
        st.dataframe(df_totales.style.apply(
            lambda x: [f'background-color: #BA8E23; color: white; font-weight: bold; font-size: 18px' if x.name == 'GRAN TOTAL (COPA)' else 'font-size: 16px' for _ in x], 
            axis=1
        ), use_container_width=True)

else:
    # Renderizado de Armas específicas
    arma, gen = diapositiva_actual.split("_")
    estado_cat = estados.get(diapositiva_actual, "EN CURSO")
    
    esgrimistas_cat = [e for e in db.get("Esgrimistas", []) if e["arma"] == arma and e["genero"] == gen]
    
    # Ajuste dinámico de encabezados según el estado
    if estado_cat == "FINALIZADA":
        st.markdown(f"## 🔴 RESULTADOS FINALES: {arma} - {gen}")
        st.markdown(f"**Atletas Inscritos:** {len(esgrimistas_cat)} &nbsp;&nbsp;|&nbsp;&nbsp; **Estado:** CATEGORÍA CERRADA OFICIALMENTE")
    else:
        max_ronda = 0
        for e in db.get("Encuentros_Equipos", []):
            if e["arma"] == arma and e["genero"] == gen:
                r_str = e["ronda"]
                if r_str.startswith("R") and r_str[1:].isdigit():
                    num = int(r_str[1:])
                    if num > max_ronda: max_ronda = num
        ronda_actual = f"Ronda {max_ronda + 1}" if max_ronda > 0 else "Ronda 1"
        st.markdown(f"## 🟢 EN PISTA: {arma} - {gen}")
        st.markdown(f"**Atletas Inscritos:** {len(esgrimistas_cat)} &nbsp;&nbsp;|&nbsp;&nbsp; **Fase del Torneo:** {ronda_actual}")
    
    def calcular_tablas_tv(rk_arma, rk_gen, db, estado):
        # 1. Procesamiento de Equipos
        teams_stats = {}
        for e in db.get("Encuentros_Equipos", []):
            if e["arma"] == rk_arma and e["genero"] == rk_gen:
                eid = e["id_encuentro"]
                eq1 = e["id_escuela_1_3"]
                eq2 = e["id_escuela_4_6"]
                for eq in [eq1, eq2]:
                    if eq not in teams_stats:
                        teams_stats[eq] = {"pj": 0, "pg": 0, "td": 0, "tr": 0, "v_indiv": 0}
                
                bouts_entry = next((b for b in db.get("Asaltos_Bouts", []) if b["id_encuentro"] == eid), None)
                if bouts_entry and len(bouts_entry.get("bouts", [])) > 0:
                    td1 = sum(b["toques_a"] for b in bouts_entry["bouts"])
                    td2 = sum(b["toques_b"] for b in bouts_entry["bouts"])
                    teams_stats[eq1]["pj"] += 1; teams_stats[eq2]["pj"] += 1
                    teams_stats[eq1]["td"] += td1; teams_stats[eq1]["tr"] += td2
                    teams_stats[eq2]["td"] += td2; teams_stats[eq2]["tr"] += td1
                    
                    if td1 > td2: teams_stats[eq1]["pg"] += 1
                    elif td2 > td1: teams_stats[eq2]["pg"] += 1
                    
                    # Conteo de Victorias en Combates Individuales dentro del equipo
                    for b in bouts_entry["bouts"]:
                        if b["toques_a"] > b["toques_b"]: teams_stats[eq1]["v_indiv"] += 1
                        elif b["toques_b"] > b["toques_a"]: teams_stats[eq2]["v_indiv"] += 1
                        
        tabla_eq = [{"Escuela": eq.replace("_", " "), "PJ": s["pj"], "PG": s["pg"], "V. Indiv.": s["v_indiv"], "TD": s["td"], "Índice": s["td"]-s["tr"]} for eq, s in teams_stats.items()]
        df_eq = pd.DataFrame(tabla_eq)
        if not df_eq.empty:
            df_eq = df_eq.sort_values(by=["PG", "Índice", "TD"], ascending=False).reset_index(drop=True)
            df_eq.index = df_eq.index + 1
            # Inyectar Puntos CISM si la categoría está cerrada
            if estado == "FINALIZADA":
                pts_eq = {1: 15, 2: 12, 3: 10, 4: 8, 5: 6}
                df_eq["Puntos CISM"] = [pts_eq.get(i, 0) for i in df_eq.index]
            
        # 2. Procesamiento Individual
        esg_ag = [es for es in db.get("Esgrimistas", []) if es["arma"] == rk_arma and es["genero"] == rk_gen]
        ind_stats = {es["id_esgrimista"]: {"nombre": es["nombre"], "v": 0, "m": 0, "td": 0, "tr": 0} for es in esg_ag}
        
        for p in db.get("Poules_Ronda0", []):
            if p["arma"] == rk_arma and p["genero"] == rk_gen:
                esc_p_id = p["escuela"].replace(" ", "_").upper()
                t_p = [es for es in esg_ag if es["id_escuela"] == esc_p_id and es.get("estado_competencia", "Activo") == "Activo"]
                if len(t_p) >= 3:
                    for b in p.get("bouts", []):
                        ia, ib, ta, tb = b["t_idx_a"], b["t_idx_b"], b["toques_a"], b["toques_b"]
                        id_a, id_b = t_p[ia]["id_esgrimista"], t_p[ib]["id_esgrimista"]
                        ind_stats[id_a]["m"] += 1; ind_stats[id_a]["td"] += ta; ind_stats[id_a]["tr"] += tb
                        if ta > tb: ind_stats[id_a]["v"] += 1
                        ind_stats[id_b]["m"] += 1; ind_stats[id_b]["td"] += tb; ind_stats[id_b]["tr"] += ta
                        if tb > ta: ind_stats[id_b]["v"] += 1

        for b_entry in db.get("Asaltos_Bouts", []):
            enc = next((e for e in db.get("Encuentros_Equipos", []) if e["id_encuentro"] == b_entry["id_encuentro"]), None)
            if enc and enc["arma"] == rk_arma and enc["genero"] == rk_gen:
                sust = b_entry.get("sustituciones", {})
                m1 = {str(i+1): eid for i, eid in enumerate(enc['alineacion_1_3'])}
                m2 = {str(i+4): eid for i, eid in enumerate(enc['alineacion_4_6'])}
                r1 = next((es["id_esgrimista"] for es in esg_ag if es["id_escuela"] == enc["id_escuela_1_3"] and es["nombre"] == enc.get("reserva_1_3")), None)
                r2 = next((es["id_esgrimista"] for es in esg_ag if es["id_escuela"] == enc["id_escuela_4_6"] and es["nombre"] == enc.get("reserva_4_6")), None)
                for b in b_entry.get("bouts", []):
                    m_num, cruce, ta, tb = b["asalto"], b["cruce"], b["toques_a"], b["toques_b"]
                    if "-" in cruce:
                        n_a, n_b = cruce.split("-")
                        id_a = r1 if (sust.get("eq1_activo") and n_a == sust.get("eq1_pos") and m_num >= int(sust.get("eq1_desde", 99)) and r1) else m1.get(n_a)
                        id_b = r2 if (sust.get("eq2_activo") and n_b == sust.get("eq2_pos") and m_num >= int(sust.get("eq2_desde", 99)) and r2) else m2.get(n_b)
                        if id_a and id_a in ind_stats:
                            ind_stats[id_a]["m"] += 1; ind_stats[id_a]["td"] += ta; ind_stats[id_a]["tr"] += tb
                            if ta > tb: ind_stats[id_a]["v"] += 1
                        if id_b and id_b in ind_stats:
                            ind_stats[id_b]["m"] += 1; ind_stats[id_b]["td"] += tb; ind_stats[id_b]["tr"] += ta
                            if tb > ta: ind_stats[id_b]["v"] += 1

        tabla_indiv = [{"Atleta": s["nombre"], "V/M": round(s["v"]/s["m"], 3) if s["m"]>0 else 0, "TD": s["td"], "Índice": s["td"]-s["tr"]} for eid, s in ind_stats.items() if s["m"] > 0]
        df_ind = pd.DataFrame(tabla_indiv)
        
        if not df_ind.empty:
            df_ind = df_ind.sort_values(by=["V/M", "Índice", "TD"], ascending=False).reset_index(drop=True)
            ganador_guardado = db.get("Desempates", {}).get(f"{rk_arma}_{rk_gen}")
            if ganador_guardado:
                df_ind["Prioridad"] = df_ind["Atleta"].apply(lambda x: 1 if x == ganador_guardado else 0)
                df_ind = df_ind.sort_values(by=["Prioridad", "V/M", "Índice", "TD"], ascending=[False, False, False, False]).drop(columns=["Prioridad"]).reset_index(drop=True)
            df_ind.index = df_ind.index + 1
            
            # Inyectar Puntos CISM si la categoría está cerrada
            if estado == "FINALIZADA":
                def pts_indiv(pos):
                    if pos == 1: return 10
                    if pos == 2: return 7
                    if pos == 3: return 5
                    if pos == 4: return 4
                    if pos == 5: return 3
                    if pos == 6: return 2
                    if 7 <= pos <= 15: return 1
                    return 0
                df_ind["Puntos CISM"] = [pts_indiv(i) for i in df_ind.index]
            
        return df_eq, df_ind

    df_equipos, df_individual = calcular_tablas_tv(arma, gen, db, estado_cat)
    
    col_eq, col_ind = st.columns(2)
    with col_eq:
        st.markdown("#### 🛡️ Poule de Equipos")
        if not df_equipos.empty: st.dataframe(df_equipos, use_container_width=True)
        else: st.info("Esperando resultados de pista.")
        
    with col_ind:
        st.markdown("#### 🤺 Gran Poule Individual")
        if not df_individual.empty: st.dataframe(df_individual, use_container_width=True)
        else: st.info("Esperando resultados de pista.")

# Inserción del pie de página inamovible al final del ciclo
st.markdown("<div class='footer-text'>Sistema de Gestión CISM Chile v4.6, diseñado por el maestro José De Sousa</div>", unsafe_allow_html=True)

# Avanzar el carrusel para el próximo ciclo y esperar
st.session_state.tv_index += 1
time.sleep(15)
st.rerun()