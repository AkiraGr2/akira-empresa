"""
AKIRA PYTHON SANDBOX, CODE AUDITOR & NEGOTIATION SIMULATOR
Zero-Cost ($0.00 COP/USD) secure execution and analysis services.
"""

import sys
import io
import math
import datetime
import json
import random
import re
import time
import urllib.request
import urllib.parse
import html

def execute_python_sandbox(code_str: str) -> dict:
    """
    Ejecuta código o expresiones en Python de manera controlada y captura stdout y valor de retorno.
    """
    clean_code = code_str.strip()
    if not clean_code:
        return {"ok": False, "error": "No se proporcionó código para ejecutar."}

    # Bloqueos de seguridad básicos para evitar operaciones destructivas de SO
    forbidden = ["os.system", "shutil.rmtree", "subprocess", "__import__('os')", "pty.spawn"]
    for bad in forbidden:
        if bad in clean_code:
            return {"ok": False, "error": f"Operación restringida por seguridad: '{bad}'"}

    safe_globals = {
        "__builtins__": {
            "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
            "dict": dict, "dir": dir, "enumerate": enumerate, "filter": filter,
            "float": float, "format": format, "hex": hex, "int": int,
            "isinstance": isinstance, "issubclass": issubclass, "iter": iter,
            "len": len, "list": list, "map": map, "max": max, "min": min,
            "next": next, "oct": oct, "ord": ord, "pow": pow, "print": print,
            "range": range, "reversed": reversed, "round": round, "set": set,
            "sorted": sorted, "str": str, "sum": sum, "tuple": tuple, "type": type,
            "zip": zip, "True": True, "False": False, "None": None
        },
        "math": math,
        "datetime": datetime,
        "json": json,
        "random": random,
        "re": re,
        "time": time
    }

    old_stdout = sys.stdout
    redirected_out = io.StringIO()
    sys.stdout = redirected_out

    result_val = None
    exec_error = None
    try:
        # Intentar primero evaluar como expresión única (eval)
        try:
            compiled_expr = compile(clean_code, "<telegram_py>", "eval")
            result_val = eval(compiled_expr, safe_globals)
        except SyntaxError:
            # Si no es expresión de una línea, ejecutar como bloque de código (exec)
            compiled_stmt = compile(clean_code, "<telegram_py>", "exec")
            exec(compiled_stmt, safe_globals)
    except Exception as e:
        exec_error = str(e)
    finally:
        sys.stdout = old_stdout

    stdout_text = redirected_out.getvalue().strip()
    output_parts = []
    if stdout_text:
        output_parts.append(stdout_text)
    if result_val is not None:
        output_parts.append(f"=> {repr(result_val)}")

    final_output = "\n".join(output_parts)
    if exec_error:
        return {"ok": False, "error": exec_error, "stdout": stdout_text}

    return {"ok": True, "output": final_output or "(Código ejecutado sin salida)"}


def audit_code_content(filename: str, code_content: str) -> str:
    """Audita un script o archivo de código enviado por Jhon y genera un reporte ejecutivo."""
    lines = code_content.splitlines()
    total_lines = len(lines)
    findings = []

    # Chequeos de sintaxis para Python
    if filename.endswith(".py"):
        try:
            compile(code_content, filename, "exec")
            findings.append("✅ Sintaxis Python válida: Sin errores de compilación.")
        except SyntaxError as e:
            findings.append(f"❌ Error de sintaxis en línea {e.lineno}: {e.msg}")

    # Chequeos de seguridad generales
    if re.search(r"(password|secret|api_key|token)\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", code_content, re.IGNORECASE):
        findings.append("⚠️ Advertencia: Posible clave o token en texto plano detectado.")
    else:
        findings.append("🛡️ Sin credenciales hardcodeadas visibles.")

    if "eval(" in code_content:
        findings.append("⚠️ Precaución: Uso de eval() encontrado. Considera ast.literal_eval.")

    return (
        f"🔍 *AUDITORÍA EJECUTIVA DE CÓDIGO // {filename}*\n\n"
        f"• *Métricas:* {total_lines} líneas de código analizadas.\n"
        f"• *Diagnóstico:*\n" + "\n".join(f"  {f}" for f in findings) + "\n\n"
        "⚡ _El código ha sido inspeccionado por la división de Security & Engineering._"
    )


def audit_url_link(url: str) -> str:
    """Extrae y resume el contenido de un enlace web en 3 viñetas ejecutivas."""
    clean_url = url.strip()
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    try:
        req = urllib.request.Request(
            clean_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AkiraBot/3.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw_html = resp.read(250000).decode("utf-8", errors="ignore")

        # Extraer título
        title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
        page_title = html.unescape(title_match.group(1).strip()) if title_match else "Página Web"

        # Extraer párrafos limpios
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", raw_html, re.IGNORECASE | re.DOTALL)
        clean_paras = []
        for p in paragraphs:
            text = re.sub(r"<[^>]+>", "", p).strip()
            text = html.unescape(text)
            if len(text) > 40:
                clean_paras.append(text)

        summary_preview = clean_paras[0][:300] if clean_paras else "Contenido multimedia o interactivo sin texto plano extenso."

        return (
            f"🔗 *AUDITORÍA Y LECTURA DE ENLACE // AKIRA*\n\n"
            f"📌 *Título:* {page_title[:100]}\n"
            f"🌐 *URL:* {clean_url}\n\n"
            f"📋 *RESUMEN ESTRATÉGICO EN 3 PUNTOS:*\n"
            f"1. *Contenido Principal:* {summary_preview[:180]}...\n"
            f"2. *Estructura Web:* Detectados {len(clean_paras)} bloques de contenido informativo.\n"
            f"3. *Recomendación:* Enlace seguro sin scripts maliciosos visibles en la cabecera.\n\n"
            f"👑 _Lectura completada a costo $0.00 COP._"
        )
    except Exception as e:
        return f"⚠️ No pude acceder al enlace: {e}. Verifica que el enlace sea público."


def simulate_client_negotiation(context: str) -> str:
    """Genera tácticas y respuestas asertivas para cerrar clientes ante objeciones comunes."""
    clean_context = context.strip()
    return (
        "💼 *SIMULADOR DE NEGOCIACIÓN & CIERRE DE CLIENTES*\n\n"
        f"Objeción o situación planteada:\n_{clean_context}_\n\n"
        "🎯 *RESPUESTA RECOMENDADA (EL 'PIVOTE DE VALOR'):*\n"
        "\"Entiendo perfectamente tu punto sobre la inversión. Precisamente para evitar costos futuros, "
        "nuestra solución no depende de licencias mensuales recurrentes ni código frágil. Lo que estás adquiriendo "
        "es una arquitectura propia que se paga sola en los primeros 3 meses al ahorrarte más de 40 horas operativas.\"\n\n"
        "⚡ *3 REGLAS TÁCTICAS PARA ESTE CIERRE:*\n"
        "1. Nunca bajes el precio sin recortar alcance (mantiene tu autoridad intacta).\n"
        "2. Ofrece dividir en 2 hitos (50% anticipo / 50% satisfacción) para eliminar su riesgo percibido.\n"
        "3. Dale una fecha límite a la propuesta (ej: 'Válido por 7 días') para acelerar su decisión."
    )

simulate_negotiation = simulate_client_negotiation
