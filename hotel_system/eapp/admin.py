from datetime import datetime
from flask import redirect, request
from flask_admin import Admin, BaseView, expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_login import logout_user, current_user
from wtforms.fields.numeric import FloatField, IntegerField
from eapp import app, db, dao
from eapp.models import AccountRole, RoomType, Room, Regulation

# add admin index and room management views
class MyAdminIndex(AdminIndexView):
    @expose('/')
    def index(self):
        return self.render('admin/index.html', stats=dao.count_rooms_by_type())

admin = Admin(app=app, name='Aurelia Hotel Admin', index_view=MyAdminIndex())

class ManagerAuthenticated(ModelView):
    def is_accessible(self) -> bool:
        return current_user.is_authenticated and current_user.user_role == AccountRole.MANAGER

class RoomTypeView(ManagerAuthenticated):
    column_list = ['id', 'name', 'base_price', 'description']
    column_searchable_list = ['name']
    edit_modal = True
    form_overrides = {'base_price': FloatField}

class RoomView(ManagerAuthenticated):
    column_list = ['id', 'room_number', 'room_type', 'status', 'image']
    column_searchable_list = ['room_number']
    column_filters = ['status', 'room_type_id']
    edit_modal = True
    can_view_details = True

# add regulation management view
class RegulationView(ManagerAuthenticated):
    can_create = False
    can_delete = False
    edit_modal = True
    column_list = ['max_guests', 'extra_guest_rate', 'foreign_guest_factor', 'max_hold_days', 'deposit_rate']
    form_overrides = {
        'max_guests': IntegerField,
        'extra_guest_rate': FloatField,
        'foreign_guest_factor': FloatField,
        'max_hold_days': IntegerField,
        'deposit_rate': FloatField
    }

# add monthly stats view and register admin views
class BaseManagerAuthenticated(BaseView):
    def is_accessible(self) -> bool:
        return current_user.is_authenticated and current_user.user_role == AccountRole.MANAGER


class StatsView(BaseManagerAuthenticated):
    @expose('/')
    def index(self):
        month = int(request.args.get('month', datetime.now().month))
        year = int(request.args.get('year', datetime.now().year))

        revenue_stats = dao.stats_revenue_by_room_type(month=month, year=year)
        occupancy_stats = dao.stats_occupancy_by_room(month=month, year=year)

        return self.render('admin/stats.html',
                           revenue_stats=revenue_stats,
                           occupancy_stats=occupancy_stats,
                           selected_month=month,
                           selected_year=year)


class LogoutView(BaseManagerAuthenticated):
    @expose('/')
    def index(self):
        logout_user()
        return redirect('/admin')


admin.add_view(RoomTypeView(RoomType, db.session, name='Loại phòng'))
admin.add_view(RoomView(Room, db.session, name='Danh sách phòng'))
admin.add_view(RegulationView(Regulation, db.session, name='Quy định (UC01)'))
admin.add_view(StatsView(name='Thống kê báo cáo (UC04)'))
admin.add_view(LogoutView(name='Đăng xuất'))
