from datetime import datetime
from flask import redirect, request
from flask_admin import Admin, BaseView, expose, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_login import logout_user, current_user
from wtforms.fields.numeric import FloatField, IntegerField
from eapp import app, db, dao
from eapp.models import AccountRole, RoomType, Room, Regulation, CustomerType


class MyAdminIndex(AdminIndexView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == AccountRole.MANAGER

    def inaccessible_callback(self, name, **kwargs):
        if not current_user.is_authenticated:
            return redirect('/login?next=' + request.url)
        return redirect('/')

    @expose('/')
    def index(self):
        return self.render('admin/index.html', stats=dao.stats_rooms_by_type())

admin = Admin(app=app, name='Aurelia Hotel Admin', index_view=MyAdminIndex())


class ManagerAuthenticated(ModelView):
    def is_accessible(self) -> bool:
        return current_user.is_authenticated and current_user.role == AccountRole.MANAGER


class RoomTypeView(ManagerAuthenticated):
    column_list = ['id', 'name', 'base_price', 'description']
    column_searchable_list = ['name']
    edit_modal = True
    form_overrides = {'base_price': FloatField}


class CustomerTypeView(ManagerAuthenticated):
    column_list = ['id', 'name', 'coefficient']
    column_labels = {'name': 'Loại khách', 'coefficient': 'Hệ số'}
    form_excluded_columns = ['customers']
    edit_modal = True
    form_overrides = {'coefficient': FloatField}


class RoomView(ManagerAuthenticated):
    column_list = ['id', 'room_number', 'room_type', 'price', 'status', 'note']
    column_labels = {'room_number': 'Phòng', 'room_type': 'Loại phòng', 'price': 'Đơn giá',
                     'status': 'Tình trạng', 'note': 'Ghi chú'}
    column_formatters = {'price': lambda view, context, model, name: "{:,.0f}".format(model.price)}
    column_searchable_list = ['room_number']
    column_filters = ['status', 'room_type_id']
    edit_modal = True
    can_view_details = True
    can_export = True


class RegulationView(ManagerAuthenticated):
    can_create = False
    can_delete = False
    edit_modal = True
    column_list = ['max_guests', 'extra_guest_rate', 'max_hold_days', 'deposit_rate', 'manager_id', 'updated_date']
    form_excluded_columns = ['manager', 'updated_date']
    form_overrides = {
        'max_guests': IntegerField,
        'extra_guest_rate': FloatField,
        'max_hold_days': IntegerField,
        'deposit_rate': FloatField
    }

    def on_model_change(self, form, model, is_created):
        model.manager_id = current_user.user_id


class BaseManagerAuthenticated(BaseView):
    def is_accessible(self) -> bool:
        return current_user.is_authenticated and current_user.role == AccountRole.MANAGER


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
admin.add_view(CustomerTypeView(CustomerType, db.session, name='Loại khách'))
admin.add_view(RegulationView(Regulation, db.session, name='Quy định (UC01)'))
admin.add_view(StatsView(name='Thống kê báo cáo'))
admin.add_view(LogoutView(name='Đăng xuất'))
