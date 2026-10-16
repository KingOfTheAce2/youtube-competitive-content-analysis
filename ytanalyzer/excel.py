"""Excel output."""

from .common import *

def save_to_excel(videos: list[dict], analytics: dict, channel_info: dict, output_path: str) -> None:
    if not EXCEL_AVAILABLE:
        print("Excel export skipped (pip install openpyxl)")
        return

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Overview"

    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    ws['A1'] = f"Analysis: {channel_info.get('title', '')}"
    ws['A1'].font = Font(bold=True, size=16)

    health = analytics.get('health_score', {})
    ws['A3'] = f"Health Score: {health.get('total_score', 0):.0f}/100 (Grade: {health.get('grade', 'N/A')})"

    overview_data = [
        ("Subscribers", format_number(channel_info.get('subscriber_count', 0))),
        ("Videos", analytics.get('overview', {}).get('total_videos_analyzed', 0)),
        ("Total Views", format_number(analytics.get('overview', {}).get('total_views', 0))),
        ("Avg Virality", f"{analytics.get('overview', {}).get('average_virality_score', 0):.4f}"),
        ("Est. Revenue", format_currency(analytics.get('revenue_analysis', {}).get('total_estimated_mid', 0))),
    ]

    for i, (label, value) in enumerate(overview_data, start=5):
        ws[f'A{i}'] = label
        ws[f'B{i}'] = value

    # Videos sheet
    ws_videos = wb.create_sheet("Videos")
    fields = ['video_id', 'title', 'view_count', 'virality_score', 'estimated_revenue_mid']
    for col, field in enumerate(fields, 1):
        cell = ws_videos.cell(row=1, column=col, value=field)
        cell.fill = header_fill
        cell.font = header_font

    for row, v in enumerate(sorted(videos, key=lambda x: x['view_count'], reverse=True), 2):
        for col, field in enumerate(fields, 1):
            ws_videos.cell(row=row, column=col, value=v.get(field, ''))

    wb.save(output_path)
    print(f"Saved Excel: {output_path}")

