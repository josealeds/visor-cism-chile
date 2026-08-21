import streamlit as st
import pandas as pd
import requests
import time

# --- CONFIGURACIÓN PARA PANTALLA DE TV ---
st.set_page_config(page_title="Visor TV - CISM", layout="wide", initial_sidebar_state="collapsed")

# REEMPLAZA ESTO CON TU URL EXACTA
DB_URL = "https://torneo-cism-default-rtdb.firebaseio.com/torneo_db.json"

# Estilos CSS para Pantalla Gigante (TV)
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    h1 { text-align: center; color: #BA8E23; font-size: 3rem !important; text-transform: uppercase; margin-bottom: 0px; }
    h2 { text-align: center; color: #ecf0f1; font-size: 2rem !important; margin-top: 0px; }
    .estado-box { text-align: center; font-size: 1.5rem; font-weight: bold; padding: 10px; border-radius: 10px; margin-bottom: 20px;}
    .en-curso { background-color: #27ae60; color: white; }
    .finalizada { background-color: #c0392b; color: white; }
    
    /* Aumentar tamaño de tablas para TV */
    div[data-testid="stDataFrame"] { font-size: 1.2rem; }
    </style>
""", unsafe_allow_html=True)

def cargar_db():
    try:
        r = requests.get(DB_URL)
        if r.status_code == 200 and r.json():
            return r.json()
    except:
        pass
    return {}

db = cargar_db()

# --- MOTOR MATEMÁTICO V4.7 (IDÉNTICO A LA MESA DE CONTROL) ---
def calcular_ranking_equipos_tv(db_ref, arma, genero):
    teams = set()
    for e in db_ref.get("Encuentros_Equipos", []):
        if e["arma"] == arma and e["genero"] == genero:
            teams.add(e["id_escuela_1_3"]); teams.add(e["id_escuela_4_6"])
    teams = list(teams)
    
    match_results = {t: {} for t in teams}
    bouts_won = {t: {} for t in teams}
    td_dict = {t: {} for t in teams}
    tr_dict = {t: {} for t in teams}
    
    equipos_expulsados = db_ref.get("Equipos_Expulsados", [])
    
    for e in db_ref.get("Encuentros_Equipos", []):
        if e["arma"] == arma and e["genero"] == genero:
            eq1, eq2, eid = e["id_escuela_1_3"], e["id_escuela_4_6"], e["id_encuentro"]
            is_eq1_exp = f"{eq1}_{arma}_{genero}" in equipos_expulsados
            is_eq2_exp = f"{eq2}_{arma}_{genero}" in equipos_expulsados
            
            bouts_entry = next((b for b in db_ref.get("Asaltos_Bouts", []) if b["id_encuentro"] == eid), None)
            
            if is_eq1_exp and not is_eq2_exp:
                match_results[eq1][eq2] = eq2; match_results[eq2][eq1] = eq2
                bouts_won[eq1][eq2], bouts_won[eq2][eq1] = 0, 9
                td_dict[eq1][eq2], td_dict[eq2][eq1] = 0, 45
                tr_dict[eq1][eq2], tr_dict[eq2][eq1] = 45, 0
            elif is_eq2_exp and not is_eq1_exp:
                match_results[eq1][eq2] = eq1; match_results[eq2][eq1] = eq1
                bouts_won[eq1][eq2], bouts_won[eq2][eq1] = 9, 0
                td_dict[eq1][eq2], td_dict[eq2][eq1] = 45, 0
                tr_dict[eq1][eq2], tr_dict[eq2][eq1] = 0, 45
            elif is_eq1_exp and is_eq2_exp:
                match_results[eq1][eq2] = None
                bouts_won[eq1][eq2], bouts_won[eq2][eq1] = 0, 0
                td_dict[eq1][eq2], td_dict[eq2][eq1] = 0, 0
                tr_dict[eq1][eq2], tr_dict[eq2][eq1] = 0, 0
            else:
                if bouts_entry and len(bouts_entry.get("bouts", [])) > 0:
                    td1 = sum(b["toques_a"] for b in bouts_entry["bouts"])
                    td2 = sum(b["toques_b"] for b in bouts_entry["bouts"])
                    bw1 = sum(1 for b in bouts_entry["bouts"] if b["toques_a"] > b["toques_b"])
                    bw2 = sum(1 for b in bouts_entry["bouts"] if b["toques_b"] > b["toques_a"])
                    
                    if td1 > td2: match_results[eq1][eq2], match_results[eq2][eq1] = eq1, eq1
                    elif td2 > td1: match_results[eq1][eq2], match_results[eq2][eq1] = eq2, eq2
                        
                    bouts_won[eq1][eq2], bouts_won[eq2][eq1] = bw1, bw2
                    td_dict[eq1][eq2], td_dict[eq2][eq1] = td1, td2
                    tr_dict[eq1][eq2], tr_dict[eq2][eq1] = td2, td1

    overall_stats = {t: {'pg': 0, 'bw': 0, 'td': 0, 'tr': 0, 'ind': 0, 'expulsado': f"{t}_{arma}_{genero}" in equipos_expulsados} for t in teams}
    for t1 in teams:
        for t2 in teams:
            if t1 == t2: continue
            if match_results.get(t1, {}).get(t2) == t1: overall_stats[t1]['pg'] += 1
            overall_stats[t1]['bw'] += bouts_won.get(t1, {}).get(t2, 0)
            overall_stats[t1]['td'] += td_dict.get(t1, {}).get(t2, 0)
            overall_stats[t1]['tr'] += tr_dict.get(t1, {}).get(t2, 0)
        overall_stats[t1]['ind'] = overall_stats[t1]['td'] - overall_stats[t1]['tr']

    active_teams = [t for t in teams if not overall_stats[t]['expulsado']]
    expelled_teams = [t for t in teams if overall_stats[t]['expulsado']]

    def group_by_metric(teams_list, metric_dict):
        grouped = {}
        for t in teams_list:
            val = metric_dict[t]
            if val not in grouped: grouped[val] = []
            grouped[val].append(t)
        return [grouped[val] for val in sorted(grouped.keys(), reverse=True)]

    def resolve_tie(tied_group):
        if len(tied_group) <= 1: return [tied_group]
        internal_pg = {t: sum(1 for t2 in tied_group if t!=t2 and match_results.get(t, {}).get(t2) == t) for t in tied_group}
        groups = group_by_metric(tied_group, internal_pg)
        if len(groups) > 1: return [res for g in groups for res in resolve_tie(g)]
        
        internal_bw = {t: sum(bouts_won.get(t, {}).get(t2, 0) for t2 in tied_group if t!=t2) for t in tied_group}
        groups = group_by_metric(tied_group, internal_bw)
        if len(groups) > 1: return [res for g in groups for res in resolve_tie(g)]
        
        internal_ind = {t: sum(td_dict.get(t, {}).get(t2, 0) - tr_dict.get(t, {}).get(t2, 0) for t2 in tied_group if t!=t2) for t in tied_group}
        groups = group_by_metric(tied_group, internal_ind)
        if len(groups) > 1: return [res for g in groups for res in resolve_tie(g)]
        
        overall_bw_metric = {t: overall_stats[t]['bw'] for t in tied_group}
        groups = group_by_metric(tied_group, overall_bw_metric)
        if len(groups) > 1: return [res for g in groups for res in resolve_tie(g)]
        
        overall_ind_metric = {t: overall_stats[t]['ind'] for t in tied_group}
        groups = group_by_metric(tied_group, overall_ind_metric)
        if len(groups) > 1: return [res for g in groups for res in resolve_tie(g)]
        
        overall_td_metric = {t: overall_stats[t]['td'] for t in tied_group}
        groups = group_by_metric(tied_group, overall_td_metric)
        if len(groups) > 1: return [res for g in groups for res in resolve_tie(g)]
        
        return [tied_group]
        
    initial_groups = group_by_metric(active_teams, {t: overall_stats[t]['pg'] for t in active_teams})
    final_ranking = []
    for g in initial_groups: final_ranking.extend(resolve_tie(g))
    if expelled_teams: final_ranking.append(expelled_teams)
        
    return final_ranking, overall_stats

def calcular_ranking_individual_tv(db_ref, rk_arma, rk_gen):
    esgrimistas_arma_gen = [es for es in db_ref.get("Esgrimistas", []) if es["arma"] == rk_arma and es["genero"] == rk_gen]
    if not esgrimistas_arma_gen: return pd.DataFrame(), pd.DataFrame()
    
    ind_stats = {es["id_esgrimista"]: {"nombre": es["nombre"], "escuela": es["id_escuela"], "v": 0, "m_real": 0, "td": 0, "tr": 0} for es in esgrimistas_arma_gen}
    
    for p in db_ref.get("Poules_Ronda0", []):
        if p["arma"] == rk_arma and p["genero"] == rk_gen:
            esc_p_id = p["escuela"].replace(" ", "_").upper()
            tiradores_p = [es for es in esgrimistas_arma_gen if es["id_escuela"] == esc_p_id and es.get("estado_competencia", "Activo") == "Activo"]
            if len(tiradores_p) >= 3:
                for b in p.get("bouts", []):
                    ia, ib, ta, tb = b["t_idx_a"], b["t_idx_b"], b["toques_a"], b["toques_b"]
                    id_a, id_b = tiradores_p[ia]["id_esgrimista"], tiradores_p[ib]["id_esgrimista"]
                    ind_stats[id_a]["m_real"] += 1; ind_stats[id_a]["td"] += ta; ind_stats[id_a]["tr"] += tb
                    if ta > tb: ind_stats[id_a]["v"] += 1
                    ind_stats[id_b]["m_real"] += 1; ind_stats[id_b]["td"] += tb; ind_stats[id_b]["tr"] += ta
                    if tb > ta: ind_stats[id_b]["v"] += 1

    for b_entry in db_ref.get("Asaltos_Bouts", []):
        enc_id = b_entry["id_encuentro"]
        enc = next((e for e in db_ref.get("Encuentros_Equipos", []) if e["id_encuentro"] == enc_id), None)
        if enc and enc["arma"] == rk_arma and enc["genero"] == rk_gen:
            sust = b_entry.get("sustituciones", {})
            map_1_3_ids = {str(i+1): eid for i, eid in enumerate(enc['alineacion_1_3'])}
            map_4_6_ids = {str(i+4): eid for i, eid in enumerate(enc['alineacion_4_6'])}
            res1 = next((es["id_esgrimista"] for es in esgrimistas_arma_gen if es["id_escuela"] == enc["id_escuela_1_3"] and es["nombre"] == enc.get("reserva_1_3")), None)
            res2 = next((es["id_esgrimista"] for es in esgrimistas_arma_gen if es["id_escuela"] == enc["id_escuela_4_6"] and es["nombre"] == enc.get("reserva_4_6")), None)
            
            for b in b_entry.get("bouts", []):
                m_num, cruce, ta, tb = b["asalto"], b["cruce"], b["toques_a"], b["toques_b"]
                if "-" in cruce:
                    n_a, n_b = cruce.split("-")
                    id_a = res1 if (sust.get("eq1_activo") and n_a == sust.get("eq1_pos") and m_num >= int(sust.get("eq1_desde", 99)) and res1) else map_1_3_ids.get(n_a)
                    id_b = res2 if (sust.get("eq2_activo") and n_b == sust.get("eq2_pos") and m_num >= int(sust.get("eq2_desde", 99)) and res2) else map_4_6_ids.get(n_b)
                    
                    if id_a and id_a in ind_stats:
                        ind_stats[id_a]["m_real"] += 1; ind_stats[id_a]["td"] += ta; ind_stats[id_a]["tr"] += tb
                        if ta > tb: ind_stats[id_a]["v"] += 1
                    if id_b and id_b in ind_stats:
                        ind_stats[id_b]["m_real"] += 1; ind_stats[id_b]["td"] += tb; ind_stats[id_b]["tr"] += ta
                        if tb > ta: ind_stats[id_b]["v"] += 1

    enc_creados = {}
    for enc in db_ref.get("Encuentros_Equipos", []):
        if enc["arma"] == rk_arma and enc["genero"] == rk_gen:
            e1, e2 = enc["id_escuela_1_3"], enc["id_escuela_4_6"]
            enc_creados[e1] = enc_creados.get(e1, 0) + 1
            enc_creados[e2] = enc_creados.get(e2, 0) + 1
            
    max_encuentros = max(enc_creados.values()) if enc_creados else 0
    m_maximo_global = 2 + (max_encuentros * 3)

    tabla_gran_poule = []
    for id_esg, st_esg in ind_stats.items():
        if st_esg["m_real"] > 0:
            v_m_global = round(st_esg["v"] / m_maximo_global, 4) if m_maximo_global > 0 else 0.0
            ind_esg = st_esg["td"] - st_esg["tr"]
            tabla_gran_poule.append({
                "Atleta": st_esg["nombre"], "Escuela": st_esg["escuela"].replace("_", " "),
                "V/M": v_m_global, "Ind": ind_esg, "TD": st_esg["td"]
            })
            
    df_gran_poule = pd.DataFrame(tabla_gran_poule)
    if df_gran_poule.empty: return pd.DataFrame(), pd.DataFrame()
    
    df_gran_poule = df_gran_poule.sort_values(by=["V/M", "Ind", "TD"], ascending=False).reset_index(drop=True)
    
    ganador_guardado = db_ref.get("Desempates", {}).get(f"{rk_arma}_{rk_gen}")
    if ganador_guardado:
        df_gran_poule["Prioridad_Oro"] = df_gran_poule["Atleta"].apply(lambda x: 1 if x == ganador_guardado else 0)
        df_gran_poule = df_gran_poule.sort_values(by=["Prioridad_Oro", "V/M", "Ind", "TD"], ascending=[False, False, False, False]).drop(columns=["Prioridad_Oro"]).reset_index(drop=True)
        
    df_gran_poule["Posición"] = df_gran_poule[["V/M", "Ind", "TD"]].apply(tuple, axis=1).rank(method='min', ascending=False).astype(int)
    if ganador_guardado and len(df_gran_poule) > 1 and df_gran_poule.iloc[0]["Atleta"] == ganador_guardado:
        df_gran_poule.at[0, "Posición"] = 1
        df_gran_poule.at[1, "Posición"] = 2
        
    activos, expulsados = [], []
    for _, row in df_gran_poule.iterrows():
        est = next((e["estado_competencia"] for e in db_ref["Esgrimistas"] if e["nombre"] == row["Atleta"]), "Activo")
        if est == "Expulsado":
            row["V/M"] = "EXCLUIDO"
            row["Posición"] = "-"
            expulsados.append(row)
        else:
            activos.append(row)
            
    df_a = pd.DataFrame(activos)
    if not df_a.empty: df_a = df_a.set_index("Posición")
    df_e = pd.DataFrame(expulsados)
    if not df_e.empty: df_e = df_e.set_index("Posición")
    
    return df_a, df_e

# --- RENDERIZADO ROTATORIO DE TV ---
if not db.get("Configuracion_Torneo"):
    st.markdown("<h1>INTERESCUELAS MATRICES CISM 2026</h1>", unsafe_allow_html=True)
    st.markdown("<h2>Esperando configuración desde la Mesa de Control...</h2>", unsafe_allow_html=True)
else:
    nom_t = db["Configuracion_Torneo"][0].get("nombre_torneo", "Torneo CISM")
    st.markdown(f"<h1>{nom_t}</h1>", unsafe_allow_html=True)
    
    # Motor de rotación
    categorias = [("Espada", "Masculino"), ("Espada", "Femenino"), 
                  ("Florete", "Masculino"), ("Florete", "Femenino"), 
                  ("Sable", "Masculino"), ("Sable", "Femenino")]
    
    if 'tv_idx' not in st.session_state:
        st.session_state.tv_idx = 0
        
    cat_actual = categorias[st.session_state.tv_idx]
    arma_act, gen_act = cat_actual
    
    st.markdown(f"<h2>Resultados en Vivo: {arma_act.upper()} {gen_act.upper()}</h2>", unsafe_allow_html=True)
    
    llave_estado = f"{arma_act}_{gen_act}"
    estado_actual = db.get("Estado_Categorias", {}).get(llave_estado, "EN CURSO")
    
    if estado_actual == "FINALIZADA":
        st.markdown('<div class="estado-box finalizada">🔴 CATEGORÍA FINALIZADA OFICIALMENTE</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="estado-box en-curso">🟢 COMPETENCIA EN CURSO (Resultados Parciales)</div>', unsafe_allow_html=True)
    
    col_izq, col_der = st.columns(2)
    
    # --- RENDER EQUIPOS ---
    with col_izq:
        st.subheader("🛡️ Clasificación Equipos")
        ranking_groups, eq_stats = calcular_ranking_equipos_tv(db, arma_act, gen_act)
        
        if ranking_groups:
            llave_des_eq = f"{arma_act}_{gen_act}"
            ganador_eq = db.get("Desempates_Equipos", {}).get(llave_des_eq)
            if ganador_eq and len(ranking_groups[0]) > 1 and ganador_eq in ranking_groups[0]:
                perdedores = [e for e in ranking_groups[0] if e != ganador_eq]
                ranking_groups[0] = [ganador_eq] + perdedores
                
            flat_ranking = []
            for g in ranking_groups: flat_ranking.extend(g)
            
            tabla_eq = []
            for eq in flat_ranking:
                s_eq = eq_stats[eq]
                if s_eq["expulsado"]:
                    tabla_eq.append({"Escuela": eq.replace("_", " "), "V": "EXPULSADO", "Ind": "-"})
                else:
                    tabla_eq.append({"Escuela": eq.replace("_", " "), "V": s_eq["pg"], "Ind": s_eq["ind"]})
            
            df_eq = pd.DataFrame(tabla_eq)
            df_eq.index = range(1, len(df_eq) + 1)
            st.dataframe(df_eq, use_container_width=True)
        else:
            st.write("Aún no hay combates registrados.")

    # --- RENDER INDIVIDUAL ---
    with col_der:
        st.subheader("🤺 Gran Poule Individual")
        df_activos, df_expulsados = calcular_ranking_individual_tv(db, arma_act, gen_act)
        
        if not df_activos.empty:
            df_mostrar = df_activos[["Atleta", "Escuela", "V/M", "Ind"]]
            st.dataframe(df_mostrar, use_container_width=True)
            
        if not df_expulsados.empty:
            st.markdown("<p style='color:#c0392b; font-weight:bold;'>Sancionados (Fuera de Ranking):</p>", unsafe_allow_html=True)
            df_exp = df_expulsados[["Atleta", "Escuela", "V/M"]]
            st.dataframe(df_exp, use_container_width=True)
            
        if df_activos.empty and df_expulsados.empty:
            st.write("Aún no hay asaltos registrados.")

    # Temporizador para rotar la categoría y actualizar
    time.sleep(12) # Cambia de pantalla cada 12 segundos
    st.session_state.tv_idx = (st.session_state.tv_idx + 1) % len(categorias)
    st.rerun()
