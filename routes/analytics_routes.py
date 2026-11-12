from flask import Blueprint, render_template, request, Response, session, abort
from routes.admin_routes import admin_required
from services.analytics_service import get_analytics_data, export_table_to_csv

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics')
@admin_required
def index():
    community_id = request.args.get('community_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    status_filter = request.args.get('status')

    kpis, charts, all_communities = get_analytics_data(
        community_id=community_id,
        start_date=start_date,
        end_date=end_date,
        status_filter=status_filter
    )

    return render_template(
        'analytics/index.html',
        kpis=kpis,
        charts=charts,
        communities=all_communities,
        current_community_id=community_id,
        current_start_date=start_date,
        current_end_date=end_date,
        current_status=status_filter
    )

@analytics_bp.route('/analytics/export/<table_name>')
@admin_required
def export_csv(table_name):
    csv_data = export_table_to_csv(table_name)
    if csv_data is None:
        abort(404)

    filename = f"mukolend_{table_name}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
