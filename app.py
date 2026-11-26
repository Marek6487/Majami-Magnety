import io
import qrcode
import os
import uuid
import time
from datetime import datetime
from pathlib import Path
import shutil
import zipfile



import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageOps
import streamlit as st
ADMIN_TOKEN = "Majami198521"

if st.query_params.get("admin") == ADMIN_TOKEN:
    st.session_state["admin_authenticated"] = True
    
from streamlit_cropper import st_cropper


def make_qr_png_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url.strip())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

st.set_page_config(
    page_title="Majami Laser – Fotomagnetky",
    page_icon="🧲",
    layout="wide",
)

BASE_DIR = Path(__file__).parent
ORDERS_DIR = BASE_DIR / "objednavky"
ORDERS_DIR.mkdir(exist_ok=True)

ADMIN_PASSWORD = "Majami198521"

BACKUP_DIR = ORDERS_DIR.parent / "zalohy_objednavok"

def create_orders_backup_zip() -> tuple[Path, int]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = BACKUP_DIR / f"zaloha_magnetky_{timestamp}.zip"

    order_folders = [p for p in ORDERS_DIR.iterdir() if p.is_dir()]
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for folder in sorted(order_folders):
            for file_path in folder.rglob("*"):
                if file_path.is_file():
                    arcname = Path(folder.name) / file_path.relative_to(folder)
                    zf.write(file_path, arcname=str(arcname))

    return zip_path, len(order_folders)

def delete_printed_orders(orders_list: list[dict]) -> int:
    deleted_count = 0
    for o in orders_list:
        if o.get("printed"):
            order_dir = ORDERS_DIR / str(o["id"])
            if order_dir.exists() and order_dir.is_dir():
                shutil.rmtree(order_dir)
                deleted_count += 1
    return deleted_count

# Názov tvojho PDF podkladu na A4
TEMPLATE_PATHS = {
    1: BASE_DIR / "sablona 1.pdf",
    2: BASE_DIR / "sablona 2.pdf",
    3: BASE_DIR / "sablona 3.pdf",
    4: BASE_DIR / "sablona 4.pdf",
    5: BASE_DIR / "sablona 5.pdf",
}

# Rozmery v milimetroch (A4 = 210 x 297 mm)
A4_W_MM = 210.0
A4_H_MM = 297.0
DPI = 300


def mm_to_px(mm: float) -> int:
    return int(round((mm / 25.4) * DPI))


def mm_to_pt(mm: float) -> float:
    return (mm / 25.4) * 72.0


# Rozmery vnútornej fotky (69 x 94 mm)
INNER_W_MM = 69.0
INNER_H_MM = 94.0

# 5 pozícií na A4 (x_mm, y_mm, w_mm, h_mm, rot)
SLOTS_MM = [
    {"x": 12.0, "y": 13.5,  "w": 94.0, "h": 69.0, "rot": 0},    # 1. vľavo hore
    {"x": 12.0,  "y": 112.8, "w": 94.0, "h": 69.0, "rot": 0},    # 2. vľavo stred
    {"x": 12.0,  "y": 215.0, "w": 94.0, "h": 69.0, "rot": 0},    # 3. vľavo dole
    {"x": 129.5, "y": 12.0,  "w": 69.0, "h": 94.0, "rot": 0},   # 4. vpravo hore
    {"x": 129.5, "y": 190.0, "w": 69.0, "h": 94.0, "rot": 0},   # 5. vpravo dole
]

SLOTS_4_MM = [
    {"x": 20.1,  "y": 12.0,  "w": 69.0, "h": 94.0, "rot": 0},    # 1. vľavo hore
    {"x": 120.3, "y": 12.0,  "w": 69.0, "h": 94.0, "rot": 0},    # 2. vpravo hore
    {"x": 20.1,  "y": 191.01, "w": 69.0, "h": 94.0, "rot": 0},    # 3. vľavo dole
    {"x": 120.3, "y": 191.01, "w": 69.0, "h": 94.0, "rot": 0},    # 4. vpravo dole
]

SLOTS_1_MM = [
    {"x": 20.1,  "y": 12.0,  "w": 69.0, "h": 94.0, "rot": 0},    # 1 foto
]

SLOTS_2_MM = [
    {"x": 20.1,  "y": 12.0, "w": 69.0, "h": 94.0, "rot": 0},   # 1. fotka (ľavý rámček)
    {"x": 120.3, "y": 12.0, "w": 69.0, "h": 94.0, "rot": 0},   # 2. fotka (pravý rámček)
]

SLOTS_3_MM = [
    {"x": 20.1, "y": 12.0,  "w": 69.0, "h": 94.0, "rot": 0},   # 1. vľavo hore (nastojato)
    {"x": 120.3, "y": 12.0, "w": 69.0, "h": 94.0, "rot":  0},   # 2. vľavo stred (naležato)
    {"x": 20.1, "y": 191.01, "w": 69.0, "h": 94.0, "rot": 0},   # 3. vľavo dole (nastojato)
]
SLOTS_BY_COUNT = {
    5: SLOTS_MM,
    4: SLOTS_4_MM,
    3: SLOTS_3_MM,
    2: SLOTS_2_MM,
    1: SLOTS_1_MM,
}

LABEL_POS_BY_COUNT = {
    1: {
        0: (50.0, 4.0),
    },
    2: {
        0: (50.0, 4.0),
        1: (150.0, 4.0),
    },
    3: {
        0: (50.0, 4.0),     # 1. fotka (vľavo hore)
        1: (150.0, 4.0),    # 2. fotka (vpravo hore)
        2: (50.0, 183.0),   # 3. fotka (vľavo dole)
    },
    4: {
        0: (50.0, 4.0),
        1: (150.0, 4.0),
        2: (50.0, 183.0),
        3: (150.0, 183.0),
    },
    5: {
        0: (52.0, 5.0),
        1: (52.0, 104.8),
        2: (52.0, 206.6),
        3: (160, 4.0),
        4: (160, 182.0),
    },
}


def load_orders():
    orders = []
    for folder in sorted(ORDERS_DIR.iterdir(), reverse=True):
        if folder.is_dir():
            meta_file = folder / "meta.txt"
            img_file = folder / "cropped.png"
            if meta_file.exists() and img_file.exists():
                lines = meta_file.read_text(encoding="utf-8").splitlines()
                meta = {}
                for line in lines:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        meta[k] = v
                orders.append({
                    "id": folder.name,
                    "name": meta.get("name", "Zákazník"),
                    "qty": int(meta.get("qty", "1")),
                    "orient": meta.get("orient", "portrait"),
                    "time": meta.get("time", ""),
                    "printed": meta.get("printed", "false") == "true",
                    "img_path": img_file,
                    "meta_path": meta_file,
                })
    return orders


def mark_printed(order_id: str, printed: bool = True):
    meta_file = ORDERS_DIR / order_id / "meta.txt"
    if meta_file.exists():
        lines = meta_file.read_text(encoding="utf-8").splitlines()
        new_lines = [l for l in lines if not l.startswith("printed=")]
        new_lines.append(f"printed={'true' if printed else 'false'}")
        meta_file.write_text("\n".join(new_lines), encoding="utf-8")


def fit_photo_to_slot(photo: Image.Image, orient: str, slot: dict) -> tuple[Image.Image, int, int, int, int]:
    target_w_px = mm_to_px(slot["w"])
    target_h_px = mm_to_px(slot["h"])

    rot = int(slot.get("rot", 0)) % 360
    if rot != 0:
        photo = photo.rotate(rot, expand=True)

    photo_is_landscape = (orient == "landscape") or (photo.width > photo.height)
    slot_is_landscape = target_w_px > target_h_px

    if photo_is_landscape != slot_is_landscape:
        photo = photo.rotate(90, expand=True)

    fitted = ImageOps.fit(
        photo,
        (target_w_px, target_h_px),
        method=Image.Resampling.LANCZOS,
    )

    px = mm_to_px(slot["x"])
    py = mm_to_px(slot["y"])
    return fitted, px, py, target_w_px, target_h_px


def render_a4_pdf(slot_items: list[dict], summary_names: list[str]) -> bytes:
    count = len(slot_items)
    active_template = TEMPLATE_PATHS.get(count, TEMPLATE_PATHS[5])
    active_slots = SLOTS_BY_COUNT.get(count, SLOTS_MM)

    if not active_template.exists():
        active_template = TEMPLATE_PATHS[5]

    if not active_template.exists():
        raise FileNotFoundError(f"Nenašiel sa súbor šablóny: {active_template}")

    # Render PDF šablóny na 300 DPI obrázok
    doc = fitz.open(str(active_template))
    page = doc[0]
    zoom = DPI / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    sheet_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    sheet_img = sheet_img.resize((mm_to_px(A4_W_MM), mm_to_px(A4_H_MM)), Image.Resampling.LANCZOS)
    doc.close()

    sheet_label_pos = LABEL_POS_BY_COUNT.get(count, {})
    draw = ImageDraw.Draw(sheet_img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    for idx, slot in enumerate(active_slots):
        if idx >= len(slot_items) or slot_items[idx] is None:
            continue

        item = slot_items[idx]
        photo = ImageOps.exif_transpose(Image.open(item["img_path"])).convert("RGB")
        orient = item.get("orient", "portrait")

        fitted, px, py, w_px, h_px = fit_photo_to_slot(photo, orient, slot)
        sheet_img.paste(fitted, (px, py))

        label_text = item.get("label", f"Foto {idx + 1}")
        if idx in sheet_label_pos:
            x_mm, y_mm = sheet_label_pos[idx]
            lx = mm_to_px(x_mm)
            ly = mm_to_px(y_mm)
        else:
            lx = px
            ly = max(mm_to_px(4.0), py - mm_to_px(8.0))

        draw.text((lx, ly), label_text, fill=(0, 0, 0), font=font)

    # Uloženie výsledného hárku do PDF (210 x 297 mm)
    out_doc = fitz.open()
    out_page = out_doc.new_page(width=mm_to_pt(A4_W_MM), height=mm_to_pt(A4_H_MM))

    img_buf = io.BytesIO()
    sheet_img.save(img_buf, format="JPEG", quality=95, dpi=(DPI, DPI))
    img_buf.seek(0)

    rect = fitz.Rect(0, 0, mm_to_pt(A4_W_MM), mm_to_pt(A4_H_MM))
    out_page.insert_image(rect, stream=img_buf.getvalue())

    pdf_bytes = out_doc.tobytes()
    out_doc.close()
    return pdf_bytes


def render_multi_page_a4_pdf(all_items: list[dict], summary_names: list[str]) -> bytes:
    chunks = [all_items[i : i + 5] for i in range(0, len(all_items), 5)]
    merged_doc = fitz.open()

    for chunk in chunks:
        single_pdf_bytes = render_a4_pdf(chunk, summary_names)
        part_doc = fitz.open(stream=single_pdf_bytes, filetype="pdf")
        merged_doc.insert_pdf(part_doc)
        part_doc.close()

    out_bytes = merged_doc.tobytes()
    merged_doc.close()
    return out_bytes


# --- HLAVNÉ ROZHRANIE ---
st.title("🧲 Majami Laser – Rýchla objednávka a tlač magnetiek")

tab_customer, tab_admin = st.tabs(["📱 Zákazník (QR upload)", "🖨️ Obsluha & Tlač A4"])

with tab_customer:
    st.subheader("Nahrajte svoju fotku na magnetku")
    st.caption("Vnútorný rozmer fotky: 6,9 × 9,4 cm (celkový výrez 8,7 × 11,2 cm vrátane okraja na zahnutie).")

            
    if "pocitadlo_nahratia" not in st.session_state:
        st.session_state["pocitadlo_nahratia"] = 0

    col1, col2 = st.columns(2)
    with col1:
        customer_name = st.text_input(
            "Vaše meno (alebo číslo objednávky)",
            placeholder="napr. Peter / stôl 3",
            key=f"meno_{st.session_state['pocitadlo_nahratia']}",
        )
    with col2:
        qty = st.number_input(
            "Počet kusov rovnakej fotky",
            min_value=1,
            max_value=20,
            value=1,
            step=1,
            key=f"qty_{st.session_state['pocitadlo_nahratia']}",
        )

    orient = st.radio(
        "Orientácia fotky",
        options=["portrait", "landscape"],
        format_func=lambda x: "Na výšku (6,9 × 9,4 cm)" if x == "portrait" else "Na šírku (9,4 × 6,9 cm)",
        horizontal=True,
    )

    uploaded_file = st.file_uploader(
        "Vyberte fotku z telefónu",
        type=["jpg", "jpeg", "png", "webp"],
        key=f"nahratie_{st.session_state['pocitadlo_nahratia']}",
    )

    if uploaded_file is not None:
        raw_img = Image.open(uploaded_file)
        raw_img = ImageOps.exif_transpose(raw_img).convert("RGB")

        preview_img = raw_img.copy()
        preview_img.thumbnail((600, 600))

        aspect = (65, 90) if orient == "portrait" else (90, 65)

        st.markdown("Upravte výrez fotky (posuňte alebo zmeňte veľkosť rámčeka):")
        crop_box = st_cropper(
            preview_img,
            realtime_update=True,
            box_color="#FF4B4B",
            aspect_ratio=aspect,
            return_type="box",
            key=f"cropper_{st.session_state['pocitadlo_nahratia']}",
        )

        if orient == "portrait":
            final_w, final_h = mm_to_px(INNER_W_MM), mm_to_px(INNER_H_MM)
        else:
            final_w, final_h = mm_to_px(INNER_H_MM), mm_to_px(INNER_W_MM)

        scale_x = raw_img.width / preview_img.width
        scale_y = raw_img.height / preview_img.height

        left = max(0, int(round(crop_box["left"] * scale_x)))
        top = max(0, int(round(crop_box["top"] * scale_y)))
        right = min(raw_img.width, int(round((crop_box["left"] + crop_box["width"]) * scale_x)))
        bottom = min(raw_img.height, int(round((crop_box["top"] + crop_box["height"]) * scale_y)))

        cropped_raw = raw_img.crop((left, top, right, bottom))
        final_img = cropped_raw.resize((final_w, final_h), Image.Resampling.LANCZOS)
        st.image(final_img, caption="Náhľad výsledného orezu na magnetku", width=240)

        if st.button("✅ Odoslať fotku na výrobu", type="primary", use_container_width=True):
            clean_name = customer_name.strip() if customer_name.strip() else "Zákazník"
            order_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:5]}"
            order_folder = ORDERS_DIR / order_id
            order_folder.mkdir(parents=True, exist_ok=True)
            
            final_img.save(order_folder / "cropped.png", format="PNG", dpi=(DPI, DPI))
            meta_content = "\n".join([
                f"name={clean_name}",
                f"qty={int(qty)}",
                f"orient={orient}",
                f"time={datetime.now().strftime('%H:%M:%S')}",
                "printed=false",
            ])
            (order_folder / "meta.txt").write_text(meta_content, encoding="utf-8")

            st.session_state["pocitadlo_nahratia"] += 1
            st.session_state["odoslane_od"] = time.time() + 0.2
            st.session_state["odoslane_do"] = time.time() + 3.2
            st.rerun()


    if uploaded_file is None:
        teraz = time.time()
        if st.session_state.get("odoslane_od", 0) <= teraz < st.session_state.get("odoslane_do", 0):
            st.markdown(
                """
                <div style="
                    background-color: #FF4B4B;
                    color: white;
                    padding: 12px 16px;
                    border-radius: 8px;
                    font-weight: 600;
                    text-align: center;
                    margin-top: 8px;
                    margin-bottom: 10px;
                ">
                    Odoslané
                </div>
                """,
                unsafe_allow_html=True,
            )
            time.sleep(0.25)
            st.rerun()
        elif teraz < st.session_state.get("odoslane_od", 0):
            time.sleep(0.1)
            st.rerun()
        else:
            st.session_state.pop("odoslane_od", None)
            st.session_state.pop("odoslane_do", None)




    else:
        if st.session_state.get("ukaz_odoslane"):
            st.markdown(
                """
                <div style="
                    background-color: #FF4B4B;
                    color: white;
                    padding: 12px 16px;
                    border-radius: 8px;
                    font-weight: 600;
                    text-align: center;
                    margin-top: 8px;
                    margin-bottom: 10px;
                ">
                    Odoslané
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.session_state["ukaz_odoslane"] = False
            time.sleep(3.0)
            st.rerun()

        else:
            st.session_state.pop("faza_odoslania", None)
            st.session_state.pop("odoslane_do", None)
            st.query_params["auth"] = get_admin_token()
with tab_admin:

    if not st.session_state.get("admin_authenticated"):
            st.markdown("### Prihlásenie pre obsluhu")
            pwd = st.text_input("Zadaj heslo:", type="password", key="admin_pwd_input")
            if st.button("Prihlásiť sa", key="admin_login_btn"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state["admin_authenticated"] = True
                    st.query_params["admin"] = ADMIN_TOKEN
                    st.rerun()
                else:
                    st.error("Nesprávne heslo.")
            st.stop()

        if st.button("Odhlásiť sa zo správy", key="admin_logout_btn"):
            st.session_state["admin_authenticated"] = False
            st.query_params.pop("admin", None)
            st.rerun()


    st.subheader("Prijaté fotky a generovanie hárku A4 (5 pozícií)")

    if not any(p.exists() for p in TEMPLATE_PATHS.values()):
        st.error("Chýba súbor šablóny. Vlož súbory šablón (sablona 1.pdf až sablona 5.pdf) do priečinka s aplikáciou.")

    orders = load_orders()
    unprinted = [o for o in orders if not o["printed"]]

    st.write(f"Nezotlačené položky: {len(unprinted)} | Celkom prijatých: {len(orders)}")

    if not orders:
        st.info("Zatiaľ tu nie sú žiadne prijaté fotky.")
    else:
        expanded_slots = []
        name_totals = {}
        for o in unprinted:
            name_totals[o["name"]] = name_totals.get(o["name"], 0) + o["qty"]

        name_seen = {}
        for o in unprinted:
            total_for_name = name_totals[o["name"]]
            for _ in range(o["qty"]):
                seen_idx = name_seen.get(o["name"], 0) + 1
                name_seen[o["name"]] = seen_idx
                label = (
                    f"{o['name']}"
                    if total_for_name == 1
                    else f"{o['name']} ({seen_idx}/{total_for_name})"
                )
                expanded_slots.append({
                    "order_id": o["id"],
                    "label": label,
                    "img_path": o["img_path"],
                    "orient": o["orient"],
                })

        selected_for_sheet = expanded_slots[:5]
        all_for_sheet = expanded_slots
        names_on_sheet = [s["label"] for s in all_for_sheet]

        st.markdown(f"Náhľad všetkých nezotlačených fotiek ({len(all_for_sheet)} ks, po max. 5 na stranu A4):")
        n_items = len(all_for_sheet)
        if n_items > 0:
            for row_start in range(0, n_items, 5):
                row_items = all_for_sheet[row_start : row_start + 5]
                cols = st.columns(len(row_items))
                for i, s in enumerate(row_items):
                    pos_num = row_start + i + 1
                    with cols[i]:
                        st.image(str(s["img_path"]), caption=f"Poz. {pos_num}: {s['label']}", use_container_width=True)

        if all_for_sheet and any(p.exists() for p in TEMPLATE_PATHS.values()):
            if st.button("🖨️Vygenerovať tlačové PDF (A4 - 300 DPI)", type="primary"):
                pdf_bytes = render_multi_page_a4_pdf(all_for_sheet, names_on_sheet)
                st.session_state["last_pdf"] = pdf_bytes
                st.session_state["last_pdf_slots"] = all_for_sheet

        if "last_pdf" in st.session_state:
            st.download_button(
                label="⬇️ Stiahnuť hotové PDF na tlač (A4)",
                data=st.session_state["last_pdf"],
                file_name=f"magnetky_A4_{datetime.now().strftime('%H%M%S')}.pdf",
                mime="application/pdf",
                type="primary",
            )
            if st.button("✔️ Označiť tieto položky ako vytlačené"):
                used_ids = {s["order_id"] for s in st.session_state.get("last_pdf_slots", [])}
                for oid in used_ids:
                    mark_printed(oid, True)
                st.session_state.pop("last_pdf", None)
                st.session_state.pop("last_pdf_slots", None)
                st.rerun()

        st.divider()
        st.markdown("Zoznam všetkých prijatých objednávok:")
        for o in orders[:20]:
            c1, c2, c3, c4 = st.columns([1, 3, 2, 2])
            with c1:
                st.image(str(o["img_path"]), width=64)
            with c2:
                st.write(f"{o['name']} ({o['qty']} ks)")
                st.caption(f"Čas: {o['time']}")
            with c3:
                st.write("🟢 Vytlačené" if o["printed"] else "🟡 Čaká na tlač")
            with c4:
                if o["printed"]:
                    if st.button("Vrátiť do tlače", key=f"re_{o['id']}"):
                        mark_printed(o["id"], False)
                        st.rerun()
        st.divider()
        st.markdown("### Zálohovanie prijatých fotiek")
        st.divider()
        st.markdown("### Čistenie už vytlačených objednávok")
        
        

        printed_orders = [o for o in orders if o.get("printed")]
        st.write(f"Pripravených na vymazanie (už vytlačené): *{len(printed_orders)}*")

        def _run_delete_printed():
            removed_cnt = delete_printed_orders(printed_orders)
            st.session_state["deleted_printed_count"] = removed_cnt
            st.session_state["confirm_delete_printed"] = False

        if st.session_state.get("deleted_printed_count"):
            st.success(f"Vymazaných {st.session_state.pop('deleted_printed_count')} už vytlačených objednávok.")

        if printed_orders:
            confirm_delete = st.checkbox(
                "Potvrdzujem, že mám zálohu a chcem zmazať už vytlačené objednávky z priečinka objednávok",
                key="confirm_delete_printed",
            )
            st.button(
                "🗑️ Vymazať už vytlačené objednávky",
                disabled=not confirm_delete,
                on_click=_run_delete_printed,
            )
        else:
            st.caption("Momentálne nie sú žiadne vytlačené objednávky na zmazanie.")
        if st.button("💾 Vytvoriť zálohu všetkých objednávok (.zip)"):
            zip_path, count_folders = create_orders_backup_zip()
            if count_folders == 0:
                st.warning("Nie sú tu zatiaľ žiadne priečinky objednávok na zálohovanie.")
            else:
                st.session_state["last_backup_path"] = str(zip_path)
                st.session_state["last_backup_count"] = count_folders
                st.success(f"Záloha vytvorená ({count_folders} objednávok): {zip_path.name}")

        if "last_backup_path" in st.session_state and Path(st.session_state["last_backup_path"]).exists():
            backup_file = Path(st.session_state["last_backup_path"])
            st.download_button(
                label=f"⬇️ Stiahnuť zálohu ({backup_file.name})",
                data=backup_file.read_bytes(),
                file_name=backup_file.name,
                mime="application/zip",
            )

        st.divider()
        st.markdown("### QR kód pre mobilné nahrávanie")

        qr_url = st.text_input(
         "Zadaj adresu (URL), na ktorú má QR kód viesť:",
         value="",
         placeholder="napr. https://tvoja-appka.streamlit.app",
         key="qr_target_url",
        )

        if qr_url.strip():
         qr_bytes = make_qr_png_bytes(qr_url)
         st.image(qr_bytes, caption=qr_url.strip(), width=240)
         st.download_button(
             label="⬇️ Stiahnuť QR kód (.png)",
             data=qr_bytes,
             file_name="qr_kod_fotky.png",
             mime="image/png",
         )
