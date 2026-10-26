"""
AKIRA PDF GENERATION SERVICE v1.0
Zero-Cost ($0.00 COP/USD) clean executive PDF document generator.
Works on any Python environment without external C-dependencies.
Uses PyMuPDF if available, or a robust pure-Python PDF-1.4 writer.
"""

import datetime

def _escape_pdf_text(text: str) -> str:
    """Escapa caracteres especiales para el formato PDF."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def create_executive_pdf(title: str, content: str, recipient: str = "Jhon Grimm", author: str = "Akira Ultra Cognitive Suite") -> bytes:
    """
    Genera un documento PDF ejecutivo formal con membrete, metadatos y contenido estructurado.
    Retorna los bytes del archivo PDF listo para enviar por Telegram o descargar.
    """
    # Intentar usar PyMuPDF si está instalado en producción
    try:
        import pymupdf
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842) # A4
        
        # Colores
        navy = (0.05, 0.1, 0.2)
        cyan = (0.0, 0.6, 0.8)
        gray = (0.4, 0.45, 0.5)
        black = (0.1, 0.1, 0.1)
        
        now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        
        # Membrete
        page.draw_rect(pymupdf.Rect(40, 40, 555, 44), color=cyan, fill=cyan)
        page.insert_text((40, 65), "AKIRA COGNITIVE SUITE // DOCUMENTO EJECUTIVO", fontsize=11, fontname="helv", color=cyan)
        page.insert_text((40, 90), title[:65], fontsize=16, fontname="hebo", color=navy)
        page.insert_text((40, 110), f"Destinatario: {recipient}   ·   Fecha: {now_str}   ·   Costo: $0.00 COP", fontsize=9, fontname="helv", color=gray)
        page.draw_line((40, 120), (555, 120), color=(0.85, 0.88, 0.92), width=1)
        
        # Cuerpo de texto
        y = 145
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                y += 10
                continue
            is_heading = line.startswith("#") or line.startswith("•") or line.endswith(":")
            fn = "hebo" if is_heading else "helv"
            fs = 11 if is_heading else 9.5
            col = navy if is_heading else black
            clean_l = line.lstrip("#*•- ").strip()
            
            # Ajuste de líneas largas
            words = clean_l.split()
            cur_line = ""
            for w in words:
                if len(cur_line + " " + w) > 85:
                    if y > 780:
                        page = doc.new_page(width=595, height=842)
                        y = 60
                    page.insert_text((40, y), cur_line.strip(), fontsize=fs, fontname=fn, color=col)
                    y += 14
                    cur_line = w
                else:
                    cur_line += " " + w
            if cur_line:
                if y > 780:
                    page = doc.new_page(width=595, height=842)
                    y = 60
                page.insert_text((40, y), cur_line.strip(), fontsize=fs, fontname=fn, color=col)
                y += 16
                
        # Pie de página
        page.insert_text((40, 810), f"Emitido por {author} · Presupuesto $0.00 COP · Documento Oficial", fontsize=8, fontname="helv", color=gray)
        return doc.tobytes()
    except Exception:
        pass

    # Fallback: Generador universal puro de PDF-1.4 (sin ninguna dependencia externa)
    now_str = datetime.datetime.now().strftime("%d/%m/%Y")
    stream_lines = [
        "BT",
        "/F2 10 Tf",
        "40 760 Td",
        "(AKIRA COGNITIVE SUITE // DOCUMENTO EJECUTIVO) Tj",
        "0 -22 Td",
        "/F2 16 Tf",
        f"({_escape_pdf_text(title[:60])}) Tj",
        "0 -18 Td",
        "/F1 9 Tf",
        f"(Destinatario: {_escape_pdf_text(recipient)}   -   Fecha: {now_str}   -   Inversion: $0.00 COP) Tj",
        "0 -25 Td",
    ]
    
    y = 695
    for raw_l in content.split("\n"):
        clean_l = raw_l.strip().lstrip("#*•- ")
        if not clean_l:
            stream_lines.append("0 -10 Td")
            y -= 10
            continue
        words = clean_l.split()
        cur_line = ""
        for w in words:
            if len(cur_line + " " + w) > 80:
                esc = _escape_pdf_text(cur_line.strip())
                stream_lines.append(f"0 -14 Td ({esc}) Tj")
                y -= 14
                cur_line = w
                if y < 80: break
            else:
                cur_line += " " + w
        if cur_line and y >= 80:
            esc = _escape_pdf_text(cur_line.strip())
            stream_lines.append(f"0 -14 Td ({esc}) Tj")
            y -= 14
        if y < 80:
            break
            
    stream_lines.append("0 -30 Td")
    stream_lines.append(f"(Generado por {author} - Presupuesto $0.00 COP Blindado) Tj")
    stream_lines.append("ET")
    
    stream_data = "\n".join(stream_lines).encode("latin1", errors="replace")
    
    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    
    offsets = []
    def add_obj(data_bytes):
        offsets.append(len(pdf))
        pdf.extend(data_bytes)
        pdf.extend(b"\n")
        
    add_obj(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj")
    add_obj(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj")
    add_obj(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>\nendobj")
    add_obj(f"4 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("latin1") + stream_data + b"\nendstream\nendobj")
    add_obj(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj")
    add_obj(b"6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj")
    
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)+1}\n0000000000 65535 f \n".encode("latin1"))
    for off in offsets:
        pdf.extend(f"{off:010d} 00000 n \n".encode("latin1"))
    pdf.extend(f"trailer\n<< /Size {len(offsets)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin1"))
    return bytes(pdf)
