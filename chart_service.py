"""
AKIRA CHART & INFOGRAPHIC GENERATION SERVICE
Zero-Cost ($0.00 COP/USD) pure-Python image chart engine using Pillow.
Generates executive-grade charts and diagrams formatted for mobile Telegram displays.
"""

import io
from PIL import Image, ImageDraw, ImageFont

def get_font(size: int = 16):
    """Obtiene una fuente TrueType del sistema o una de respaldo por defecto."""
    font_names = [
        "segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()

def create_metrics_chart(title: str, labels: list[str], values: list[float], subtitle: str = "Akira Suite Telemetry", unit: str = "%") -> bytes:
    """
    Genera un gráfico de barras ejecutivas de alta resolución con paleta Dark Mode / Akira Cyan.
    Retorna los bytes en formato PNG listos para sendPhoto en Telegram.
    """
    width = 900
    height = 550
    bg_color = (15, 23, 42)          # Slate 900
    panel_color = (30, 41, 59)       # Slate 800
    text_white = (248, 250, 252)     # Slate 50
    text_muted = (148, 163, 184)     # Slate 400
    cyan_bright = (0, 242, 254)      # Akira Cyan
    cyan_dark = (79, 172, 254)       # Blue Cyan
    border_color = (51, 65, 85)      # Slate 700

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Marco de tarjeta ejecutiva
    draw.rounded_rectangle([20, 20, width - 20, height - 20], radius=16, fill=panel_color, outline=border_color, width=2)

    # Tipografías
    title_font = get_font(26)
    sub_font = get_font(15)
    bar_font = get_font(16)
    val_font = get_font(17)
    watermark_font = get_font(13)

    # Cabecera
    draw.text((50, 45), title, fill=text_white, font=title_font)
    draw.text((50, 85), subtitle.upper(), fill=cyan_bright, font=sub_font)
    draw.line([(50, 115), (width - 50, 115)], fill=border_color, width=1)

    # Área de dibujo de barras
    top_y = 145
    bottom_y = height - 70
    left_x = 220
    right_x = width - 120
    chart_width = right_x - left_x

    n = max(len(labels), 1)
    bar_height = min(40, int((bottom_y - top_y) / (n * 1.6)))
    gap = int(((bottom_y - top_y) - (n * bar_height)) / (n + 1))

    max_val = max(values) if values and max(values) > 0 else 100.0

    current_y = top_y + gap
    for label, val in zip(labels, values):
        # Etiqueta lateral
        draw.text((50, current_y + (bar_height // 4)), label[:22], fill=text_white, font=bar_font)

        # Fondo de barra
        bg_bar_rect = [left_x, current_y, right_x, current_y + bar_height]
        draw.rounded_rectangle(bg_bar_rect, radius=6, fill=(15, 23, 42), outline=border_color, width=1)

        # Barra activa proporcional
        fraction = max(0.02, min(1.0, float(val) / max_val))
        fill_width = int(chart_width * fraction)
        active_rect = [left_x, current_y, left_x + fill_width, current_y + bar_height]
        draw.rounded_rectangle(active_rect, radius=6, fill=cyan_bright)

        # Valor numérico a la derecha
        val_str = f"{val:.1f}{unit}" if isinstance(val, float) else f"{val}{unit}"
        draw.text((right_x + 12, current_y + (bar_height // 4)), val_str, fill=cyan_bright, font=val_font)

        current_y += bar_height + gap

    # Pie de página / Watermark
    draw.line([(50, height - 60), (width - 50, height - 60)], fill=border_color, width=1)
    draw.text((50, height - 48), "AKIRA SUITE // SISTEMA OPERATIVO AUTÓNOMO", fill=text_muted, font=watermark_font)
    draw.text((width - 240, height - 48), "PRESUPUESTO: $0.00 COP", fill=cyan_bright, font=watermark_font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", quality=95)
    return buf.getvalue()


def create_roi_comparison_chart(project_name: str, traditional_cost_usd: float = 2400.0, akira_cost_usd: float = 600.0) -> bytes:
    """Genera infografía comparativa de ahorro y ROI entre desarrollo tradicional y Akira."""
    savings = max(0.0, traditional_cost_usd - akira_cost_usd)
    roi_multiple = (traditional_cost_usd / akira_cost_usd) if akira_cost_usd > 0 else 4.0
    labels = [
        "Desarrollo Tradicional",
        "Propuesta Akira Suite",
        "Ahorro Neto Inmediato"
    ]
    values = [traditional_cost_usd, akira_cost_usd, savings]
    return create_metrics_chart(
        title=f"Estudio Financiero & ROI: {project_name[:24]}",
        labels=labels,
        values=values,
        subtitle=f"Multiplicador de Eficiencia: {roi_multiple:.1f}x  |  Ahorro: ${savings:,.0f} USD",
        unit=" USD"
    )
