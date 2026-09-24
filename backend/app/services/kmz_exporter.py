import html
import io
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional

def _escape(text: Any) -> str:
    """Escapa strings para inserção segura em XML KML."""
    if text is None:
        return ""
    return html.escape(str(text))

def generate_kml_content(points: List[Dict[str, Any]], title: str = "Resultados de Viabilidade") -> str:
    """
    Gera o XML KML padronizado para Google Earth com estilização profissional por status:
    - Verde: Viáveis
    - Amarelo: Em Análise (Atenção / Vistoria)
    - Vermelho: Inviáveis
    """
    # Separar pontos por status
    viable_points = []
    analysis_points = []
    unviable_points = []

    for pt in points:
        st = str(pt.get("status") or pt.get("Viabilidade_Status") or "").upper()
        if st == "VIAVEL":
            viable_points.append(pt)
        elif st == "EM_ANALISE":
            analysis_points.append(pt)
        else:
            unviable_points.append(pt)

    kml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        '<Document>',
        f'  <name>{_escape(title)}</name>',
        '  <open>1</open>',
        '  <description>Relatório Geográfico de Viabilidade Técnica - Provedor ISP</description>',
        '',
        '  <!-- ESTILOS VISUAIS PARA O GOOGLE EARTH -->',
        '  <!-- 1. Viável (Verde) -->',
        '  <Style id="style_viavel">',
        '    <IconStyle>',
        '      <color>ff81b910</color>',
        '      <scale>1.1</scale>',
        '      <Icon>',
        '        <href>http://maps.google.com/mapfiles/kml/paddle/grn-circle.png</href>',
        '      </Icon>',
        '    </IconStyle>',
        '    <BalloonStyle>',
        '      <text><![CDATA[$[description]]]></text>',
        '    </BalloonStyle>',
        '  </Style>',
        '',
        '  <!-- 2. Em Análise (Amarelo / Vistoria) -->',
        '  <Style id="style_em_analise">',
        '    <IconStyle>',
        '      <color>ff0b9ef5</color>',
        '      <scale>1.25</scale>',
        '      <Icon>',
        '        <href>http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png</href>',
        '      </Icon>',
        '    </IconStyle>',
        '    <BalloonStyle>',
        '      <text><![CDATA[$[description]]]></text>',
        '    </BalloonStyle>',
        '  </Style>',
        '',
        '  <!-- 3. Inviável (Vermelho) -->',
        '  <Style id="style_inviavel">',
        '    <IconStyle>',
        '      <color>ff4444ef</color>',
        '      <scale>1.0</scale>',
        '      <Icon>',
        '        <href>http://maps.google.com/mapfiles/kml/paddle/red-circle.png</href>',
        '      </Icon>',
        '    </IconStyle>',
        '    <BalloonStyle>',
        '      <text><![CDATA[$[description]]]></text>',
        '    </BalloonStyle>',
        '  </Style>',
        ''
    ]

    def render_balloon_html(pt: Dict[str, Any], status: str, badge_color: str, badge_text: str) -> str:
        addr = pt.get("address") or pt.get("display_name") or pt.get("title") or "Endereço não informado"
        tech = pt.get("technology") or pt.get("Tecnologia") or "N/A"
        pop = pt.get("pop") or pt.get("POP_Estacao") or "N/A"
        layer = pt.get("layer_name") or pt.get("Mancha_Atendimento") or "N/A"
        dist = pt.get("distance_meters") if pt.get("distance_meters") is not None else pt.get("Distancia_Borda_Metros")
        dist_str = f"{dist}m" if dist is not None else "0m (No Perímetro)"
        msg = pt.get("message") or pt.get("Mensagem_Tecnica") or ""
        lat = pt.get("latitude") or pt.get("Latitude_Utilizada")
        lon = pt.get("longitude") or pt.get("Longitude_Utilizada")
        source = pt.get("source") or pt.get("Origem_Geometria") or "Geocode"

        return f"""
        <div style="font-family: Arial, sans-serif; font-size: 13px; line-height: 1.4; color: #1e293b; min-width: 260px; padding: 4px;">
          <div style="display: inline-block; padding: 3px 8px; border-radius: 4px; background-color: {badge_color}; color: #ffffff; font-weight: bold; font-size: 11px; margin-bottom: 8px;">
            {badge_text}
          </div>
          <div style="font-size: 14px; font-weight: bold; color: #0f172a; margin-bottom: 6px;">
            {_escape(addr)}
          </div>
          <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 6px;">
            <tr style="border-bottom: 1px solid #e2e8f0;">
              <td style="color: #64748b; padding: 4px 0;"><strong>Distância da Borda:</strong></td>
              <td style="color: #0f172a; padding: 4px 0;">{_escape(dist_str)}</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
              <td style="color: #64748b; padding: 4px 0;"><strong>Mancha Atendimento:</strong></td>
              <td style="color: #0f172a; padding: 4px 0;">{_escape(layer)}</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
              <td style="color: #64748b; padding: 4px 0;"><strong>POP / Central:</strong></td>
              <td style="color: #0f172a; padding: 4px 0;">{_escape(pop)}</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
              <td style="color: #64748b; padding: 4px 0;"><strong>Tecnologia:</strong></td>
              <td style="color: #0f172a; padding: 4px 0;">{_escape(tech)}</td>
            </tr>
            <tr style="border-bottom: 1px solid #e2e8f0;">
              <td style="color: #64748b; padding: 4px 0;"><strong>Coordenadas:</strong></td>
              <td style="color: #0f172a; padding: 4px 0;">{lat}, {lon}</td>
            </tr>
            <tr>
              <td style="color: #64748b; padding: 4px 0;"><strong>Origem Posição:</strong></td>
              <td style="color: #0f172a; padding: 4px 0;">{_escape(source)}</td>
            </tr>
          </table>
          {f'<div style="margin-top: 8px; font-size: 11px; color: #475569; background: #f8fafc; padding: 6px; border-left: 3px solid {badge_color}; border-radius: 2px;">{_escape(msg)}</div>' if msg else ''}
        </div>
        """

    def render_folder(folder_name: str, folder_points: List[Dict[str, Any]], style_id: str, badge_color: str, badge_label: str):
        if not folder_points:
            return
        kml_lines.append(f'    <Folder>')
        kml_lines.append(f'      <name>{_escape(folder_name)} ({len(folder_points)})</name>')
        kml_lines.append(f'      <open>1</open>')

        for idx, pt in enumerate(folder_points):
            lat = pt.get("latitude") if pt.get("latitude") is not None else pt.get("Latitude_Utilizada")
            lon = pt.get("longitude") if pt.get("longitude") is not None else pt.get("Longitude_Utilizada")
            if lat is None or lon is None:
                continue

            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (ValueError, TypeError):
                continue

            name = pt.get("title") or pt.get("address") or f"Ponto {idx + 1}"
            dist = pt.get("distance_meters") if pt.get("distance_meters") is not None else pt.get("Distancia_Borda_Metros")
            dist_suffix = f" [{dist}m]" if dist is not None and dist > 0 else ""

            desc_html = render_balloon_html(pt, style_id, badge_color, badge_label)

            kml_lines.append('      <Placemark>')
            kml_lines.append(f'        <name>{_escape(name)}{_escape(dist_suffix)}</name>')
            kml_lines.append(f'        <styleUrl>#{style_id}</styleUrl>')
            kml_lines.append(f'        <description><![CDATA[{desc_html}]]></description>')
            kml_lines.append('        <Point>')
            kml_lines.append(f'          <coordinates>{lon_f:.6f},{lat_f:.6f},0</coordinates>')
            kml_lines.append('        </Point>')
            kml_lines.append('      </Placemark>')

        kml_lines.append(f'    </Folder>')

    # 1. Pasta Em Análise no topo (prioridade para validação!)
    render_folder(
        folder_name="🟡 EM ANÁLISE (Vistoria / Extensão)",
        folder_points=analysis_points,
        style_id="style_em_analise",
        badge_color="#f59e0b",
        badge_label="EM ANÁLISE TÉCNICA"
    )

    # 2. Pasta Viáveis
    render_folder(
        folder_name="🟢 VIÁVEIS (Atendimento Imediato)",
        folder_points=viable_points,
        style_id="style_viavel",
        badge_color="#10b981",
        badge_label="VIABILIDADE CONFIRMADA"
    )

    # 3. Pasta Inviáveis
    render_folder(
        folder_name="🔴 INVIÁVEIS (Fora de Cobertura)",
        folder_points=unviable_points,
        style_id="style_inviavel",
        badge_color="#ef4444",
        badge_label="INVIÁVEL"
    )

    kml_lines.append('</Document>')
    kml_lines.append('</kml>')
    return "\n".join(kml_lines)


def export_points_to_kmz(
    points: List[Dict[str, Any]],
    output_path: Path,
    title: str = "Resultados de Viabilidade"
) -> Path:
    """
    Exporta a lista de pontos em formato KMZ compactado (ZIP contendo doc.kml).
    """
    kml_string = generate_kml_content(points, title=title)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
        kmz.writestr("doc.kml", kml_string.encode("utf-8"))

    return output_path
