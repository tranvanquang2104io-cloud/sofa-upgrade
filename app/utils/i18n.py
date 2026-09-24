"""
Internationalization (i18n) utility for SofaFlow.
Default language is English. Vietnamese translations are provided for all UI strings.
"""

# All UI strings: English is the key, Vietnamese is the value.
TRANSLATIONS = {
    'vi': {
        # ── Navigation ──────────────────────────────────────────────────
        'Dashboard':              'Dashboard',
        'Customers':              'Khách Hàng',
        'Orders':                 'Đơn Hàng',
        'Management':             'Quản Lý',
        'Stores':                 'Cửa Hàng',
        'Users':                  'Người Dùng',
        'Document Templates':     'Mẫu Tài Liệu',
        'Company Settings':       'Cài Đặt Công Ty',
        'Log Out':                'Đăng Xuất',

        # ── User roles ──────────────────────────────────────────────────
        'Company Admin':          'QT Công Ty',
        'Store Admin':            'QT Cửa Hàng',
        'Staff':                  'Nhân Viên',

        # ── Common actions ──────────────────────────────────────────────
        'View':                   'Xem',
        'Edit':                   'Chỉnh Sửa',
        'Save':                   'Lưu',
        'Cancel':                 'Hủy',
        'Back':                   'Quay Lại',
        'Create':                 'Tạo Mới',
        'Delete':                 'Xóa',
        'Search':                 'Tìm Kiếm',
        'Submit':                 'Gửi',
        'Previous':               'Trước',
        'Next':                   'Sau',
        'Confirm':                'Xác Nhận',
        'Close':                  'Đóng',
        'Save Changes':           'Lưu Thay Đổi',
        'Add':                    'Thêm',
        'Add Row':                'Thêm Dòng',
        'Actions':                'Thao Tác',
        'View All':               'Xem Tất Cả',
        'Create New':             'Tạo Mới',
        'No records found.':      'Chưa có dữ liệu.',
        'Active':                 'Hoạt Động',
        'Deactivate':             'Vô Hiệu',
        'Inactive':               'Không Hoạt Động',

        # ── Dashboard ───────────────────────────────────────────────────
        'Total Orders':           'Tổng Đơn Hàng',
        'In Progress':            'Đang Thực Hiện',
        'Completed':              'Hoàn Thành',
        'Cancelled':              'Đã Hủy',
        'Recent Orders':          'Đơn Hàng Gần Đây',

        # ── Order statuses ───────────────────────────────────────────────
        'New':                    'Mới Tạo',
        'Quotation Approved':     'Đã Duyệt BG',
        'Contract Signed':        'Đã Ký HĐ',
        'Delivered':              'Đã Bàn Giao',
        'Advance Paid':           'Đã Tạm Ứng',
        'Ngừng hoạt động khách hàng này? Chứng từ cũ vẫn giữ nguyên.':
            'Ngừng hoạt động khách hàng này? Chứng từ cũ vẫn giữ nguyên.',
        'Khách hàng "%(name)s" đã ngừng hoạt động. Chứng từ cũ giữ nguyên.':
            'Khách hàng "%(name)s" đã ngừng hoạt động. Chứng từ cũ giữ nguyên.',
        'Xóa hẳn mẫu này? Tệp mẫu sẽ bị xóa và không khôi phục được.':
            'Xóa hẳn mẫu này? Tệp mẫu sẽ bị xóa và không khôi phục được.',
        'Đã dùng để in chứng từ nên không xóa được':
            'Đã dùng để in chứng từ nên không xóa được',
        'Để trống một ô nghĩa là bước đó không phụ thuộc điều kiện này.':
            'Để trống một ô nghĩa là bước đó không phụ thuộc điều kiện này.',
        'Field':                  'Trường dữ liệu',
        'Preview':                'Xem trước',
        'Customer':               'Khách hàng',
        'Supplier':               'Nhà cung cấp',
        'Material':               'Vật tư',
        'Changes how the value reads - consider confirm mode':
            'Làm đổi cách đọc giá trị — nên cân nhắc chế độ xác nhận',
        'Bỏ chọn hết các ô trên một dòng là xóa quy tắc của trường đó.':
            'Bỏ chọn hết các ô trên một dòng là xóa quy tắc của trường đó.',
        'Không tìm thấy nhóm dữ liệu này': 'Không tìm thấy nhóm dữ liệu này',
        'Open the purchase order': 'Mở đơn mua hàng',
        'Open the requisition':    'Mở đề nghị mua hàng',
        'Main warehouse':         'Kho chính',
        # Finality warnings: these three actions have no undo anywhere in the
        # product, so the dialog has to say so (see REVIEW-2026Q3.md 3.2).
        'Sau khi xác nhận, phiếu này không thể sửa hoặc huỷ.':
            'Sau khi xác nhận, phiếu này không thể sửa hoặc huỷ.',
        'Sau khi xác nhận, biên bản này không thể huỷ.':
            'Sau khi xác nhận, biên bản này không thể huỷ.',
        'Sau khi duyệt, báo giá này không thể huỷ.':
            'Sau khi duyệt, báo giá này không thể huỷ.',
        # workflow rule modes
        'required':               'Bắt buộc',
        'waivable':               'Được phép bỏ qua (có lý do)',
        'optional':               'Khuyến nghị',
        'contract':               'Theo hợp đồng',
        'Whole order':            'Cả đơn hàng',
        'Not Invoiced':           'Chưa Có Hóa Đơn',
        'Not Paid':               'Chưa Thanh Toán',
        'Search by order code, job or customer...':
            'Tìm theo mã đơn, tên công việc hoặc khách hàng...',
        'Search by receipt number or supplier...':
            'Tìm theo số phiếu nhập hoặc nhà cung cấp...',
        'Use this template for all documents of this type from now on? The template currently in use will be replaced.':
            'Dùng mẫu này cho mọi chứng từ cùng loại từ nay? Mẫu đang dùng sẽ bị thay thế.',
        'Mark this plan as behind schedule?': 'Đánh dấu kế hoạch này là trễ tiến độ?',
        # process_list() / handover line acceptance
        'Done':                   'Xong',
        'Skipped':                'Đã Bỏ Qua',
        'Not Started':            'Chưa Bắt Đầu',
        'Unconfirmed':            'Chưa Xác Nhận',
        'Partially Accepted':     'Nghiệm Thu Một Phần',
        'Fully Paid':             'Đã Thanh Toán',

        # ── Table headers ────────────────────────────────────────────────
        'Order Code':             'Mã Đơn',
        'Customer':               'Khách Hàng',
        'Title':                  'Tiêu Đề',
        'Value':                  'Giá Trị',
        'Status':                 'Trạng Thái',
        'Date Created':           'Ngày Tạo',
        'Customer Code':          'Mã Khách Hàng',
        'Customer Name':          'Tên Khách Hàng',
        'Phone':                  'Số Điện Thoại',
        'Email':                  'Email',
        'City':                   'Thành Phố',
        'Action':                 'Thao Tác',
        'Store Code':             'Mã Cửa Hàng',
        'Store Name':             'Tên Cửa Hàng',
        'Manager':                'Quản Lý',
        'Username':               'Tên Đăng Nhập',
        'Full Name':              'Họ và Tên',
        'Role':                   'Vai Trò',
        'Store':                  'Cửa Hàng',
        'Document Name':          'Tên Tài Liệu',
        'Type':                   'Loại',
        'Format':                 'Định Dạng',
        'Size':                   'Kích Thước',
        'Generated':              'Ngày Tạo',

        # ── Customer pages ───────────────────────────────────────────────
        'Add Customer':           'Thêm Khách Hàng',
        'Edit Customer':          'Chỉnh Sửa Khách Hàng',
        'Customer Information':   'Thông Tin Khách Hàng',
        'Customer Code:':         'Mã Khách Hàng:',
        'Customer Name:':         'Tên Khách Hàng:',
        'Phone:':                 'Số Điện Thoại:',
        'Email:':                 'Email:',
        'Tax Code:':              'Mã Số Thuế:',
        'Tax Code':               'Mã Số Thuế',
        'Representative':         'Người Đại Diện',
        'Representative Name:':   'Họ và Tên:',
        'Representative Name':    'Họ và Tên',
        'Position:':              'Chức Vụ:',
        'Position':               'Chức Vụ',
        'Address':                'Địa Chỉ',
        'Address:':               'Địa Chỉ:',
        'City / Province:':       'Thành Phố / Tỉnh:',
        'City / Province':        'Thành Phố / Tỉnh',
        'Postal Code:':           'Mã Bưu Chính:',
        'Postal Code':            'Mã Bưu Chính',
        'Country:':               'Quốc Gia:',
        'Country':                'Quốc Gia',
        'Notes':                  'Ghi Chú',
        'Additional Notes':       'Ghi Chú Thêm',
        'Customer Orders':        'Đơn Hàng Khách Hàng',
        'Basic Information':      'Thông Tin Cơ Bản',
        'Customer / Company Name':'Tên Khách Hàng / Công Ty',
        'All Stores':             'Tất Cả Cửa Hàng',
        'No customers found.':    'Chưa có khách hàng.',
        'orders':                 'đơn',

        # ── Material management ──────────────────────────────────────────
        'Materials':                      'Nguyên Vật Liệu',
        'Material':                       'Nguyên Vật Liệu',
        'Raw material catalog for the company': 'Danh mục NVL của công ty',
        'Add Material':                   'Thêm NVL',
        'Edit Material':                  'Chỉnh Sửa NVL',
        'Material Code':                  'Mã NVL',
        'Material Image':                 'Ảnh NVL',
        'Categories':                     'Danh Mục',
        'Category':                       'Danh Mục',
        'All Categories':                 'Tất Cả Danh Mục',
        'No category':                    'Không có danh mục',
        'Material Categories':            'Danh Mục NVL',
        'Add Category':                   'Thêm Danh Mục',
        'Edit Category':                  'Chỉnh Sửa Danh Mục',
        'Group materials by type (e.g. Vải bọc, Da, Mút xốp, Gỗ khung...)': 'Nhóm NVL theo loại (VD: Vải bọc, Da, Mút xốp, Gỗ khung...)',
        'No categories yet. Add one to get started.': 'Chưa có danh mục. Tạo mới để bắt đầu.',
        'Deactivate this category?':      'Vô hiệu hóa danh mục này?',
        'Units':                          'Đơn Vị',
        'Unit':                           'Đơn Vị',
        'Units of Measure':               'Đơn Vị Tính',
        'Add Unit':                       'Thêm Đơn Vị',
        'Edit Unit':                      'Chỉnh Sửa Đơn Vị',
        'Select unit':                    'Chọn đơn vị',
        'Abbreviation':                   'Ký Hiệu',
        'Define measurement units used across all materials (e.g. m², kg, cái, cuộn...)': 'Định nghĩa đơn vị đo lường (VD: m², kg, cái, cuộn...)',
        'No units yet. Add common ones like m², kg, cái, cuộn, tấm...': 'Chưa có đơn vị. Thêm các đơn vị phổ biến như m², kg, cái, cuộn, tấm...',
        'Suggested common units for sofa manufacturing:': 'Đơn vị gợi ý cho sản xuất sofa:',
        'Deactivate this unit?':          'Vô hiệu hóa đơn vị này?',
        'Unit Price':                     'Đơn Giá',
        'Pricing & Stock':                'Giá & Tồn Kho',
        'Min Stock Alert':                'Cảnh Báo Tồn Kho Tối Thiểu',
        'Supplier Information':           'Thông Tin Nhà Cung Cấp',
        'Supplier Name':                  'Nhà Cung Cấp',
        'Supplier Contact':               'Liên Hệ NCC',
        'Phone / Email':                  'SĐT / Email',
        'Technical Specifications':       'Thông Số Kỹ Thuật',
        'Enter as JSON: {"thickness":"5mm","width":"1.4m"}': 'Nhập dạng JSON: {"thickness":"5mm","width":"1.4m"}',
        'e.g. Vải bọc nhung xanh navy':   'VD: Vải bọc nhung xanh navy',
        'Color':                          'Màu Sắc',
        'e.g. Xanh navy':                 'VD: Xanh navy',
        'Change Image':                   'Đổi Ảnh',
        'Upload Image':                   'Tải Ảnh Lên',
        'Leave empty to keep current image': 'Để trống để giữ ảnh hiện tại',
        'Inventory':                      'Tồn Kho',
        'Total Stock':                    'Tổng Tồn Kho',
        'Low Stock':                      'Sắp Hết',
        'Location':                       'Vị Trí',
        'Quantity':                       'Số Lượng',
        'Last Updated':                   'Cập Nhật Lần Cuối',
        'Update Stock':                   'Cập Nhật Tồn Kho',
        'No stock entries.':              'Chưa có dữ liệu tồn kho.',
        'Deactivate this material?':      'Vô hiệu hóa NVL này?',
        'No materials found.':            'Chưa có NVL nào.',
        'Search by name, code or supplier...': 'Tìm theo tên, mã hoặc NCC...',
        'Code':                           'Mã',
        'Total':                          'Tổng',
        'materials':                      'NVL',
        'Record Info':                    'Thông Tin Bản Ghi',
        'Created':                        'Ngày Tạo',
        'Updated':                        'Ngày Cập Nhật',
        'Sort':                           'Thứ Tự',
        'Sort Order':                     'Thứ Tự Sắp Xếp',
        'Used by':                        'Đang Dùng',

        # ── Orders pages ─────────────────────────────────────────────────
        'Create Order':           'Tạo Đơn Hàng',
        'Order Information':      'Thông Tin Đơn Hàng',
        'Order Code:':            'Mã Đơn:',
        'Customer:':              'Khách Hàng:',
        'Store:':                 'Cửa Hàng:',
        'Total Amount:':          'Giá Trị:',
        'Order Lifecycle':        'Tiến Trình Đơn Hàng',
        'No orders yet.':         'Chưa có đơn hàng.',
        'Create new':             'Tạo mới',
        'Cancel Order':           'Hủy Đơn Hàng',
        'Cancellation Reason *':  'Lý Do Hủy *',
        'Confirm Cancel':         'Xác Nhận Hủy',
        'Note:':                  'Lưu ý:',
        'Created:':               'Ngày tạo:',
        'Approved:':              'Ngày Xác nhận:',
        'Signed:':                'Ngày ký:',

        # ── Store pages ──────────────────────────────────────────────────
        'Manage Stores':          'Quản Lý Cửa Hàng',
        'Add Store':              'Thêm Cửa Hàng',
        'Add New Store':          'Thêm Cửa Hàng Mới',
        'Edit Store':             'Sửa Cửa Hàng',
        'Store Code *':           'Mã Cửa Hàng *',
        'Store Name *':           'Tên Cửa Hàng *',
        'Manager Name':           'Tên Quản Lý',
        'Address (optional)':     'Địa Chỉ',
        'City / Province (opt)':  'Thành Phố / Tỉnh',
        'Deactivate Store':       'Vô Hiệu Hóa Cửa Hàng',
        'Confirm Deactivate':     'Xác Nhận Vô Hiệu',
        'No stores found.':       'Chưa có cửa hàng.',
        'List of stores in the company': 'Danh sách cửa hàng của công ty',
        'Are you sure you want to deactivate store': 'Bạn có chắc muốn vô hiệu hóa cửa hàng',
        'This action will hide the store from the system. Data will not be deleted.': 'Thao tác này sẽ ẩn cửa hàng khỏi hệ thống. Dữ liệu sẽ không bị xóa.',
        'Add the first store to start managing.': 'Thêm cửa hàng đầu tiên để bắt đầu quản lý.',
        'users':                  'người dùng',
        'Create Store':           'Tạo Cửa Hàng',

        # ── User pages ───────────────────────────────────────────────────
        'Add User':               'Thêm Người Dùng',
        'Edit User':              'Sửa Người Dùng',
        'Full Name *':            'Họ và Tên *',
        'Username *':             'Tên Đăng Nhập *',
        'Email *':                'Email *',
        'Password *':             'Mật Khẩu *',
        'New Password':           'Mật Khẩu Mới',
        'Role *':                 'Vai Trò *',
        'Store (required for non-admin)': 'Cửa Hàng (bắt buộc)',
        'Employee':               'Nhân Viên',
        'Store Manager':          'Quản Trị Cửa Hàng',
        'Company Manager':        'Quản Trị Công Ty',
        '— Select store —':       '— Chọn cửa hàng —',
        'Leave blank to keep current password': 'Để trống nếu không đổi',
        'Create User':            'Tạo Người Dùng',

        # ── Payment pages ────────────────────────────────────────────────
        'Create Payment Record':  'Tạo Biên Bản Thanh Toán',
        'Edit Payment Record':    'Chỉnh Sửa Biên Bản',
        'Payment Record':         'Biên Bản Thanh Toán',
        'Back to Order':          'Quay lại Đơn Hàng',
        'Reference Contract':     'Hợp Đồng Tham Chiếu',
        'Load items from contract': 'Tải hạng mục từ hợp đồng',
        'Contract Value':         'Giá trị hợp đồng',
        'VAT Tax':                'Thuế VAT',
        'Get New Code':           'Lấy mã mới',
        'Advance':                'Tạm ứng',
        'Remaining':              'Còn lại thanh toán',
        'Report Number *':        'Số Biên Bản *',
        'Payment Type *':         'Loại Thanh Toán *',
        '-- Select type --':      '-- Chọn loại --',
        'Advance Payment':        'Tạm Ứng',
        'Final Payment':          'Thanh Toán Cuối',
        'Date *':                 'Ngày Lập *',
        'Payment Date *':         'Ngày Thanh Toán *',
        'Contract Sign Date':     'Ngày Ký Hợp Đồng',
        'Payment Method':         'Hình Thức Thanh Toán',
        '-- Select --':           '-- Chọn --',
        'Bank Transfer':          'Chuyển khoản ngân hàng',
        'Cash':                   'Tiền mặt',
        'Cheque':                 'Séc',
        'Work / Items Table':     'Bảng Công Việc / Hàng Hóa',
        'Click "Load items from contract" to auto-fill': 'Nhấn "Tải hạng mục từ hợp đồng" để tự động điền',
        'No.':                    'STT',
        'Item Description':       'Nội Dung Công Việc',
        'Unit':                   'ĐVT',
        'Quantity':               'Số Lượng',
        'Unit Price':             'Đơn Giá',
        'Amount':                 'Thành Tiền',
        'Subtotal:':              'Cộng tiền hàng:',
        'Payment Value:':         'Giá Trị Thanh Toán:',
        'Advance %:':             'Tạm Ứng Trước (%):',
        'Advance Amount':         'Số Tiền Tạm Ứng',
        'Remaining Amount':       'Còn Lại Phải Thanh Toán',
        'Amount in Words':        'Số Tiền Bằng Chữ',
        'Payer Info':             'Thông Tin Bên Thanh Toán',
        'Payer Name':             'Tên Bên Thanh Toán',
        'Payer Title':            'Chức Vụ',
        'Payer Address':          'Địa Chỉ',
        'Bank Account':           'Số Tài Khoản',
        'Bank Name':              'Ngân Hàng',
        'Generate Document':      'Tạo Tài Liệu',

        # ── Handover pages ───────────────────────────────────────────────
        'Create Handover Record': 'Tạo Biên Bản Bàn Giao',
        'Edit Handover Record':   'Chỉnh Sửa Biên Bản Bàn Giao',
        'Handover Record':        'Biên Bản Bàn Giao',
        'Handover Date':          'Ngày Bàn Giao',
        'Handover Location':      'Địa Điểm Bàn Giao',
        'Handover Items':         'Danh Sách Bàn Giao',
        'Item Name':              'Tên Hàng',
        'Specs / Notes':          'Thông Số / Ghi Chú',
        'Condition':              'Tình Trạng',
        'Good':                   'Tốt',
        'Delivery Person':        'Người Giao',
        'Receiver':               'Người Nhận',
        'Receiver Name':          'Tên Người Nhận',
        'Receiver Title':         'Chức Vụ',
        'Receiver Phone':         'Số Điện Thoại',
        'Handover Notes':         'Ghi Chú Bàn Giao',

        # ── Contract pages ────────────────────────────────────────────────
        'Create Contract':        'Tạo Hợp Đồng',
        'Edit Contract':          'Chỉnh Sửa Hợp Đồng',
        'Contract':               'Hợp Đồng',
        'Contract Number *':      'Số Hợp Đồng *',
        'Contract Date *':        'Ngày Ký *',
        'Contract Value *':       'Giá Trị HĐ *',
        'VAT Rate (%)':           'Thuế VAT (%)',
        'Advance %':              'Tạm Ứng (%)',
        'Contract Items':         'Hạng Mục Hợp Đồng',
        'Contract Terms':         'Điều Khoản Hợp Đồng',
        'Party A':                'Bên A',
        'Party B':                'Bên B',
        'Terms':                  'Điều Khoản',
        'Sign Date':              'Ngày Ký',
        'Contract Information':   'Thông Tin Hợp Đồng',

        # ── Quotation pages ───────────────────────────────────────────────
        'Create Quotation':       'Tạo Báo Giá',
        'Edit Quotation':         'Chỉnh Sửa Báo Giá',
        'Quotation':              'Báo Giá',
        'Quotation Number *':     'Số Báo Giá *',
        'Quotation Date *':       'Ngày Báo Giá *',
        'Valid Until':            'Hiệu Lực Đến',
        'Quotation Items':        'Hạng Mục Báo Giá',
        'Quotation Notes':        'Ghi Chú Báo Giá',
        'Quotation Information':  'Thông Tin Báo Giá',
        'Approve Quotation':      'Duyệt Báo Giá',
        'Reject Quotation':       'Từ Chối',

        # ── Auth pages ────────────────────────────────────────────────────
        'Login':                  'Đăng Nhập',
        'Register':               'Đăng Ký',
        'Company Code':           'Mã Công Ty',
        'Password':               'Mật Khẩu',
        'Remember me':            'Ghi nhớ đăng nhập',
        'Forgot password?':       'Quên mật khẩu?',

        # ── Error pages ───────────────────────────────────────────────────
        'Page Not Found':         'Không Tìm Thấy Trang',
        'Forbidden':              'Không Có Quyền Truy Cập',
        'Internal Server Error':  'Lỗi Máy Chủ',
        'Go Home':                'Về Trang Chủ',

        # ── Status badges & states ────────────────────────────────────────
        'Pending':                'Chờ Xử Lý',
        'Pending Approval':       'Chờ Duyệt',
        'Pending Confirmation':   'Chờ Xác Nhận',
        'Draft':                  'Nháp',
        'CONFIRMED':              'ĐÃ XÁC NHẬN',
        'CANCELLED':              'ĐÃ HỦY',
        'DRAFT':                  'NHÁP',
        'Confirmed':              'Đã Xác Nhận',
        'Signed':                 'Đã Ký',
        'Unsigned':               'Chưa Ký',
        'Approved':               'Đã Duyệt',
        'Rejected':               'Từ Chối',
        'Partial':                'Một Phần',
        'Accepted':               'Đã Chấp Nhận',
        'Canceled':               'Đã Hủy',
        '✓ Created':              '✓ Đã Tạo',
        '✓ Signed':               '✓ Đã Ký',
        '✓ Confirmed':            '✓ Đã Xác Nhận',
        '✓ Completed':            '✓ Hoàn Thành',
        'Draft (not yet confirmed)': 'Nháp (chưa xác nhận)',
        'Confirmed on':           'Xác nhận lúc',
        'Cancelled on':           'Hủy lúc',

        # ── Timeline / event labels ───────────────────────────────────────
        'Created:':               'Ngày Tạo:',
        'Approved:':              'Ngày Duyệt:',
        'Signed:':                'Ngày Ký:',
        'Generated:':             'Ngày Tạo:',

        # ── Page sections ─────────────────────────────────────────────────
        'Quick Actions':          'Thao Tác Nhanh',
        'Documents':              'Tài Liệu',
        'Generated Documents':    'Tài Liệu Đã Tạo',
        'Generate':               'Tạo',
        'Download':               'Tải Xuống',
        'Download as PDF':        'Tải về PDF',
        'Download as DOCX':       'Tải về DOCX',
        'Approve':                'Duyệt',
        'Line Items':             'Hạng Mục',
        'TOTAL:':                 'TỔNG:',
        'No documents generated yet': 'Chưa có tài liệu',
        'No documents generated yet.': 'Chưa có tài liệu nào.',
        'Document Format':        'Định Dạng Tài Liệu',
        'Quotation Details':      'Chi Tiết Báo Giá',
        'Contract Details':       'Chi Tiết Hợp Đồng',
        'Source Quotation':       'Báo Giá Tham Chiếu',
        'View Quotation':         'Xem Báo Giá',
        'Edit Contract':          'Chỉnh Sửa Hợp Đồng',
        'Sign Contract':          'Ký Hợp Đồng',
        'Cancel Contract':        'Hủy Hợp Đồng',
        'Cancel Quotation':       'Hủy Báo Giá',
        'Cancel Handover Record': 'Hủy Biên Bản Bàn Giao',
        'Cancel Payment':         'Hủy Thanh Toán',
        'Cancel Record':          'Hủy Biên Bản',
        'Confirm Payment':        'Xác Nhận Thanh Toán',
        'Confirm Handover':       'Xác Nhận Bàn Giao',
        'Record Advance Payment': 'Tạo Biên Bản Tạm Ứng',
        'Record Final Payment':   'Tạo Biên Bản Thanh Toán Cuối',
        'Skip Advance Payment':   'Bỏ Qua Tạm Ứng',
        'Payment Request':        'Đề Nghị Thanh Toán',

        # ── DL labels (view detail pages) ─────────────────────────────────
        'Advance:':               'Tạm Ứng:',
        'Final:':                 'Thanh Toán Cuối:',
        'Description:':           'Mô Tả:',
        'Notes:':                 'Ghi Chú:',
        'Amount:':                'Số Tiền:',
        'Date:':                  'Ngày:',
        'Status:':                'Trạng Thái:',
        'Order:':                 'Đơn Hàng:',
        'Total:':                 'Giá Trị:',
        'Order Cancelled':        'Đơn Hàng Đã Hủy',
        'Cancelled at:':          'Thời Gian Hủy:',
        'Reason:':                'Lý Do:',
        'Warning:':               'Cảnh Báo:',
        'This action cannot be undone. The order will be marked as canceled.':
                                  'Hành động này không thể hoàn tác. Đơn hàng sẽ bị đánh dấu là đã hủy.',
        'This action cannot be undone. The contract will be marked as canceled.':
                                  'Hành động này không thể hoàn tác. Hợp đồng sẽ bị đánh dấu là đã hủy.',

        # ── Quotation view ────────────────────────────────────────────────
        'Quotation Number:':      'Số Báo Giá:',
        'Validity Days:':         'Thời Hạn Hiệu Lực (ngày):',
        'Cancellation Reason:':   'Lý Do Hủy:',
        'Pending Approval':       'Chờ Duyệt',

        # ── Contract view ─────────────────────────────────────────────────
        'Contract Number:':       'Số Hợp Đồng:',
        'Contract Value:':        'Giá Trị Hợp Đồng:',
        'Signed Date:':           'Ngày Ký:',
        'Canceled At:':           'Thời Gian Hủy:',
        'Terms & Conditions':     'Điều Khoản',
        'Contract Items':         'Hạng Mục Hợp Đồng',
        'Are you sure you want to sign this contract? Once signed, it cannot be edited.':
                                  'Bạn có chắc muốn ký hợp đồng này? Sau khi ký, không thể chỉnh sửa.',
        'Contract Number:':       'Số Hợp Đồng:',

        # ── Payment view ──────────────────────────────────────────────────
        'Payment Details':        'Chi Tiết Thanh Toán',
        'Report Number:':         'Số Biên Bản:',
        'Payment Type:':          'Loại Thanh Toán:',
        'Report Date:':           'Ngày Lập:',
        'Payment Date:':          'Ngày Thanh Toán:',
        'Payment Method:':        'Hình Thức Thanh Toán:',
        'Transaction Ref:':       'Số Tham Chiếu:',
        'Are you sure you want to cancel this payment?':
                                  'Bạn có chắc muốn hủy thanh toán này?',

        # ── Handover view ─────────────────────────────────────────────────
        'Handover Details':       'Chi Tiết Bàn Giao',
        'Record Number:':         'Số Biên Bản:',
        'Handover Date:':         'Ngày Bàn Giao:',
        'Company Rep:':           'Đại Diện Công Ty:',
        'Customer Rep:':          'Đại Diện Khách Hàng:',
        'Items Acceptance':       'Danh Sách Nghiệm Thu',
        'Delivered':              'Số Bàn Giao',
        'Total':                  'Tổng Cộng',
        'Product Condition':      'Tình Trạng Hàng',
        'No description provided': 'Chưa có mô tả',
        'Are you sure you want to cancel this handover record?':
                                  'Bạn có chắc muốn hủy biên bản bàn giao này?',
        'Reason for Cancellation': 'Lý Do Hủy',
        'Enter cancellation reason...': 'Nhập lý do hủy...',

        # ── Confirmation dialogs ──────────────────────────────────────────
        'Confirm Quotation':        'Xác Nhận Báo Giá',
        'Are you sure you want to approve this quotation?': 'Bạn có chắc muốn duyệt báo giá này?',
        'Are you sure you want to confirm this handover record?': 'Bạn có chắc muốn xác nhận biên bản bàn giao này?',
        'Are you sure you want to confirm this payment?': 'Bạn có chắc muốn xác nhận thanh toán này?',
        'Approve this quotation?':  'Duyệt báo giá này?',
        'Sign this contract?':      'Ký hợp đồng này?',
        'Confirm this payment?':    'Xác nhận thanh toán này?',
        'Confirm this handover?':   'Xác nhận biên bản bàn giao này?',
        'Confirm this handover record?': 'Xác nhận biên bản bàn giao này?',
        # ── Reports (BI/KPI) ──────────────────────────────────────────────
        'Reports':                  'Báo cáo',
        'Sales':                    'Bán hàng',
        'Accounting':               'Kế toán',
        'Orders':                   'Đơn hàng',
        'In progress':              'Đang thực hiện',
        'Completed':                'Hoàn thành',
        'Booked (signed)':          'Đã ký (chốt)',
        'Cash collected':           'Đã thu',
        'Top customers':            'Khách hàng hàng đầu',
        'Value':                    'Giá trị',
        'Requisitions':             'Đề nghị mua',
        'Purchase orders':          'Đơn mua hàng',
        'Goods receipts':           'Phiếu nhập kho',
        'Open':                     'Đang mở',
        'PO value':                 'Giá trị đơn mua',
        'Received value':           'Giá trị đã nhận',
        'Outstanding (not received)': 'Còn lại (chưa nhận)',
        'Top suppliers':            'Nhà cung cấp hàng đầu',
        'Cash in':                  'Tiền vào',
        'Receivable outstanding':   'Công nợ phải thu',
        'Advance collected':        'Tạm ứng đã thu',
        'Final collected':          'Thanh toán cuối đã thu',
        'Pending confirmation':     'Chờ xác nhận',
        'document(s)':              'chứng từ',
        'Confirm Payment':          'Xác Nhận Thanh Toán',
        'Confirm that this payment has been received?': 'Xác nhận đã nhận được khoản thanh toán này?',
        'Payment proof (image/PDF)': 'Ảnh/PDF chứng từ thanh toán',
        'optional':                 'không bắt buộc',
        'Payment proof:':           'Chứng từ thanh toán:',
        'View proof':               'Xem chứng từ',
        'Also create the final payment now': 'Tạo luôn phiếu thanh toán cuối',
        'Confirms this handover and creates a draft final payment report from these items (remaining balance after advance). You can confirm and attach proof later.':
            'Xác nhận biên bản bàn giao này và tạo phiếu thanh toán cuối (nháp) từ các hạng mục (số còn lại sau tạm ứng). Bạn có thể xác nhận và đính kèm chứng từ sau.',
        'Handover record and final payment created successfully': 'Đã tạo biên bản bàn giao và phiếu thanh toán cuối',
        'Handover created, but final payment could not be created automatically': 'Đã tạo biên bản bàn giao, nhưng không thể tự động tạo phiếu thanh toán cuối',

        # ── Orders view – order sidebar ───────────────────────────────────
        'Handover':               'Bàn Giao',
        'Payment':                'Thanh Toán',

        # ── Customers list ────────────────────────────────────────────────
        'Name':                   'Tên',
        'Search by name or code...': 'Tìm theo tên hoặc mã...',
        'Add one':                'Thêm mới',

        # ── Orders / Create form ──────────────────────────────────────────
        'Store *':                'Cửa Hàng *',
        'Select a store':         'Chọn cửa hàng',
        'Customer *':             'Khách Hàng *',
        'Select a customer':      'Chọn khách hàng',
        'Order Code *':           'Mã Đơn Hàng *',
        'Order Title *':          'Tên Đơn Hàng *',
        'Description':            'Mô Tả',
        'Create Order':           'Tạo Đơn Hàng',
        'e.g., Sofa Repair':      'vd: Sửa Sofa',

        # ── Documents list ────────────────────────────────────────────────
        'Documents for':          'Tài liệu của',

        # ── Auth pages (extra) ────────────────────────────────────────────
        'Customer Lifecycle Management System': 'Hệ Thống Quản Lý Đơn Hàng',
        'Register Company':       'Đăng Ký Công Ty',
        'Create a new SofaFlow account': 'Tạo tài khoản SofaFlow mới',
        'Company Name':           'Tên Công Ty',
        'Company Email':          'Email Công Ty',
        'Your Full Name':         'Họ và Tên của Bạn',
        "Don't have an account?": 'Chưa có tài khoản?',
        'Register here':          'Đăng ký tại đây',
        'Already have an account?': 'Đã có tài khoản?',
        'Login here':             'Đăng nhập tại đây',

        # ── Error pages (extra) ──────────────────────────────────────────
        'Go to Dashboard':        'Về Dashboard',
        'Access Denied':          'Truy Cập Bị Từ Chối',
        "You don't have permission to access this resource.":
                                  'Bạn không có quyền truy cập tài nguyên này.',
        "The page you're looking for doesn't exist or has been moved.":
                                  'Trang bạn tìm không tồn tại hoặc đã bị di chuyển.',
        'Something went wrong on our end. Please try again later.':
                                  'Đã xảy ra lỗi máy chủ. Vui lòng thử lại sau.',

        # ── User management ───────────────────────────────────────────────
        'User Management':        'Quản Lý Người Dùng',
        'All company accounts':   'Tất cả tài khoản trong công ty',
        'Users at your store':    'Người dùng tại cửa hàng của bạn',
        'Last Login':             'Đăng Nhập Cuối',
        'Never':                  'Chưa Đăng Nhập',
        'Deactivate Account':     'Vô Hiệu Hóa Tài Khoản',
        'Deactivate account':     'Vô hiệu hóa tài khoản',
        'This user will no longer be able to log in.':
                                  'Người dùng này sẽ không thể đăng nhập nữa.',
        'No users yet':           'Chưa có người dùng nào',
        'Email *':                'Email *',

        # ── Company settings ──────────────────────────────────────────────
        'These details appear on all generated documents (quotations, contracts, etc.)':
                                  'Các thông tin này sẽ xuất hiện trên tất cả tài liệu được tạo.',
        'Company Name *':         'Tên Công Ty *',
        'Registered / Head-office Address': 'Địa Chỉ Đăng Ký / Trụ Sở Chính',
        'Production / Manufacturing Address': 'Địa Chỉ Sản Xuất / Nhà Máy',
        'Legal Representative':   'Người Đại Diện Pháp Lý',
        'Title / Position':       'Chức Vụ / Vị Trí',
        'Tax Settings':           'Cài Đặt Thuế',
        'Default VAT Rate (%)':   'Thuế VAT Mặc Định (%)',
        'This default is pre-filled in all new documents.':
                                  'Giá trị này sẽ được điền trước trong tất cả tài liệu mới.',
        'Bank Accounts':          'Tài Khoản Ngân Hàng',
        'Used in payment documents': 'Dùng trong tài liệu thanh toán',
        'Add Bank Account':       'Thêm Tài Khoản Ngân Hàng',
        'Save Settings':          'Lưu Cài Đặt',
        'Document Header Preview': 'Xem Trước Tiêu Đề Tài Liệu',
        'Head office:':           'Trụ sở chính:',
        'Manufacturing address:': 'Địa chỉ sản xuất:',
        'Tax Code:':              'Mã Số Thuế:',
        'Representative:':        'Người Đại Diện:',

        # ── Document templates settings ───────────────────────────────────
        'Manage document templates (.docx) for each document type':
                                  'Quản lý mẫu tài liệu (.docx) cho từng loại tài liệu',
        'Upload New Template':    'Tải Lên Mẫu Mới',
        'Template Name':          'Tên Mẫu',
        'Deactivate this template?': 'Vô hiệu hóa mẫu này?',
        'Activate':               'Kích Hoạt',
        'Upload Document Template': 'Tải Lên Mẫu Tài Liệu',
        'No document templates yet. Upload the first one.':
                                  'Chưa có mẫu tài liệu. Tải mẫu đầu tiên lên.',

        # ── Contract form fields ──────────────────────────────────────────
        'Contract Number':        'Số Hợp Đồng',
        'Contract number cannot be changed': 'Số hợp đồng không thể thay đổi',
        'Signing Date':           'Ngày Ký',
        'Signing date cannot be changed': 'Ngày ký không thể thay đổi',
        'Signing Location':       'Địa Điểm Ký',
        'Reference Quotation':    'Báo Giá Tham Chiếu',
        '-- Select quotation --': '-- Chọn báo giá --',
        'Items / Work Table':     'Bảng Hạng Mục / Công Việc',
        'Item Name / Work':       'Hạng Mục / Công Việc',
        'Qty':                    'SL',
        'Total Contract Value:':  'Tổng Giá Trị Hợp Đồng:',
        'Advance (%)':            'Tạm Ứng (%)',
        'Contract Terms & Conditions': 'Điều Khoản Hợp Đồng',
        'Create New Contract':    'Tạo Hợp Đồng Mới',
        'Cancellation Reason *':  'Lý Do Hủy *',

        # ── Quotation form fields ─────────────────────────────────────────
        'Quotation Number *':     'Số Báo Giá *',
        'Quotation Date *':       'Ngày Báo Giá *',
        'Location':               'Địa Điểm',
        'Validity (Days)':        'Thời Hạn Hiệu Lực (Ngày)',
        'Payment Terms':          'Điều Khoản Thanh Toán',
        'Grand Total:':           'Tổng Cộng:',
        'Shipping Fee':           'Chi phí vận chuyển',
        'Other Fee':              'Chi phí khác',
        'Create New Quotation':   'Tạo Báo Giá Mới',

        # ── Handover form fields ──────────────────────────────────────────
        'Start Time':             'Giờ Bắt Đầu',
        'End Time':               'Giờ Kết Thúc',
        'Number of Copies':       'Số Bản Sao',
        'Delivery Representative *': 'Đại Diện Giao Hàng *',
        'Receiving Representative *': 'Đại Diện Nhận Hàng *',
        'Handover Items Table':   'Bảng Hàng Bàn Giao',
        'Item / Work':            'Hàng Hóa / Công Việc',
        'Product Condition / Conclusion *': 'Tình Trạng Hàng / Kết Luận *',
        'Create Record':          'Tạo Biên Bản',

        # ── Payment form fields ───────────────────────────────────────────
        'Contract Signing Date':  'Ngày Ký Hợp Đồng',
        'Remaining Balance':      'Số Dư Thanh Toán',
        'Quotation Reference Date': 'Ngày Tham Chiếu',
        'Work Items / Goods':     'Công Việc / Hàng Hóa',
        'This record cannot be edited (already confirmed or cancelled)':
                                  'Biên bản này không thể chỉnh sửa (đã xác nhận hoặc đã hủy)',

        # ── Customer form fields ──────────────────────────────────────────
        'Create Customer':        'Tạo Khách Hàng',
        'Customer Code *':        'Mã Khách Hàng *',
        'Full Name / Company Name *': 'Tên / Tên Công Ty *',
        'Representative Title / Position': 'Chức Vụ Người Đại Diện',
        'No stores available.':   'Chưa có cửa hàng nào.',
        'You need to create a store first before adding customers.':
                                  'Bạn cần tạo cửa hàng trước khi thêm khách hàng.',
        'Return to Dashboard':    'Quay Lại Dashboard',

        # ── Store form fields ─────────────────────────────────────────────
        'City / Province':        'Thành Phố / Tỉnh',
        'Identifier code, cannot be changed after creation.':
                                  'Mã định danh, không thể thay đổi sau khi tạo.',

        # ── Misc ──────────────────────────────────────────────────────────
        'Loading...':             'Đang tải...',
        'This code is already in use!': 'Mã này đã được sử dụng!',
        'Code (auto-generated)':  'Mã (tự động)',
        'Switch to Vietnamese':   'Chuyển sang Tiếng Việt',
        'Switch to English':      'Chuyển sang Tiếng Anh',

        # -- Procurement & production (i18n pass, 2026-09) --
        'Add Line':                             'Thêm dòng',
        'All':                                  'Tất cả',
        'Behind schedule':                      'Trễ tiến độ',
        'Create Purchase Order':                'Tạo đơn mua',
        'Create Requisition':                   'Tạo đề nghị mua',
        'Date':                                 'Ngày',
        'Document No.':                         'Số phiếu',
        'Expected Delivery':                    'Giao dự kiến',
        'GRAND TOTAL':                          'TỔNG CỘNG',
        'Goods Receipt (GR)':                   'Phiếu nhập kho (GR)',
        'Goods receipt history':                'Lịch sử nhập kho',
        'Into Store':                           'Nhập vào kho',
        'Issue materials (deduct stock)':       'Cấp phát (trừ kho)',
        'Line Total':                           'Thành tiền',
        'Lines':                                'Số dòng',
        'Main warehouse (company)':             'Kho chính (công ty)',
        'Material Name':                        'Tên vật tư',
        'Needed By':                            'Cần trước ngày',
        'No material lines yet.':               'Chưa có dòng vật tư nào.',
        'Order Date':                           'Ngày đặt',
        'Outstanding':                          'Còn lại',
        'PO No.':                               'Số PO',
        'PR No.':                               'Số PR',
        'Print Purchase Order':                 'In đơn đặt hàng',
        'Qty Ordered':                          'SL đặt',
        'Qty Received':                         'SL nhận',
        'Qty Received Now':                     'SL nhận đợt này',
        'Receive Goods':                        'Nhập kho',
        'Received Date':                        'Ngày nhận',
        'Receiving Store':                      'Kho nhập',
        'Requested Date':                       'Ngày đề nghị',
        'Requesting Store':                     'Kho / cửa hàng cần',
        'Title / Reason':                       'Tiêu đề / lý do',
        'Total Amount':                         'Tổng tiền',

        # -- Procurement & production, pass 2 --
        '-- not assigned --':                   '— chưa gán —',
        '-- not specified --':                  '— không xác định —',
        '-- select material --':                '— chọn vật tư —',
        'Auto suggestions':                     'Đề xuất tự động',
        'Fill from auto suggestions':           'Điền từ đề xuất tự động',
        'Goods Receipts (GR)':                  'Nhập kho (GR)',
        'Materials ordered':                    'Vật tư đặt mua',
        'Materials received':                   'Vật tư đã nhận',
        'Materials requested':                  'Vật tư đề nghị mua',
        'Print production order':               'In lệnh sản xuất',
        'Purchase Order':                       'Đơn mua',
        'Purchase Orders (PO)':                 'Đơn mua hàng (PO)',
        'Purchase Requisitions (PR)':           'Đề nghị mua hàng (PR)',
        'Purchase suggestions':                 'Đề xuất mua hàng',
        'Received':                             'Đã nhận',
        'Requisitions (PR)':                    'Đề nghị mua (PR)',
        'Source':                               'Nguồn',
        'Stock increased':                      'Đã ghi tăng tồn',
        'The plan is approved and locked. The material list can no longer be changed. To edit it again, use "Reject (rework)" to return it to production status.':
            'Kế hoạch đã được chốt (duyệt). Danh mục vật tư đã khóa, không thể thêm/xóa. Muốn chỉnh sửa lại, hãy dùng “Từ chối (làm lại)” để đưa về trạng thái sản xuất.',

        # -- Procurement/production actions & confirmations --
        'Approve plan':                           'Duyệt kế hoạch',
        'Cancel order':                           'Hủy đơn',
        'Cancel plan':                            'Hủy kế hoạch',
        'Cancel this production plan?':           'Hủy kế hoạch sản xuất này?',
        'Cancel this purchase order?':            'Hủy đơn mua này?',
        'Cancel this requisition?':               'Hủy đề nghị mua này?',
        'Clear late flag':                        'Bỏ đánh dấu trễ',
        'Complete':                               'Hoàn tất',
        'Confirm goods receipt? Stock will increase.':'Xác nhận nhập kho? Tồn kho sẽ tăng.',
        'Create purchase orders from this requisition, grouped by supplier?':'Tạo đơn mua (PO) từ đề nghị này, gộp theo nhà cung cấp?',
        'Issue materials and deduct stock?':      'Cấp phát vật tư và trừ kho?',
        'Mark as behind schedule':                'Đánh dấu trễ tiến độ',
        'Production finished':                    'Đã sản xuất xong',
        'Reject (rework)':                        'Từ chối (làm lại)',
        'Reopen':                                 'Mở lại',
        'Send back for edit':                     'Trả lại (sửa)',
        'Send to supplier':                       'Gửi nhà cung cấp',
        'Start production':                       'Bắt đầu sản xuất',
        'Submit for acceptance':                  'Gửi nghiệm thu',
        'Submit for approval':                    'Gửi duyệt',
        'Withdraw to draft':                      'Thu hồi về nháp',

        # -- Confirmation dialogs & safety messages (2026-09) --
        'Send this purchase order to the supplier? Treat it as a real commitment to buy.':
            'Gửi đơn mua này cho nhà cung cấp? Hãy coi đây là cam kết mua thật sự.',
        'Withdraw this purchase order back to draft?':
            'Thu hồi đơn mua này về trạng thái nháp?',
        'Issue the order confirmation now? It records the agreed prices and counts as the signed agreement for this order.':
            'Phát hành đơn đặt hàng ngay? Chứng từ này ghi nhận giá đã thỏa thuận và có giá trị như thỏa thuận đã ký của đơn này.',
        'Approve this quotation? After approval it can no longer be edited.':
            'Duyệt báo giá này? Sau khi duyệt sẽ không sửa được nữa.',
        'Mark this contract as signed? A signed contract can no longer be edited or cancelled.':
            'Đánh dấu hợp đồng này đã ký? Hợp đồng đã ký sẽ không sửa hay hủy được nữa.',
        'Confirm this handover? It records that the customer accepted the goods and cannot be undone.':
            'Xác nhận bàn giao? Thao tác này ghi nhận khách đã nhận hàng và không thể hoàn tác.',
        'Confirm this supplier invoice? After this it can no longer be edited or cancelled.':
            'Xác nhận hóa đơn nhà cung cấp này? Sau đó sẽ không sửa hay hủy được nữa.',
        'Record this payment to the supplier? This cannot be undone.':
            'Ghi nhận khoản thanh toán cho nhà cung cấp? Thao tác này không thể hoàn tác.',
        'Change the status of this framework agreement? It affects whether new orders can be placed under it.':
            'Đổi trạng thái hợp đồng nguyên tắc này? Việc này ảnh hưởng tới việc có đặt đơn mới theo nó được hay không.',
        'Cancel this order confirmation?':
            'Hủy đơn đặt hàng này?',
        'Reason for cancelling':
            'Lý do hủy',
        'Order confirmation not found or access denied':
            'Không tìm thấy đơn đặt hàng hoặc không có quyền',
        'Please give a reason for cancelling':
            'Vui lòng nhập lý do hủy',
        'Order confirmation cancelled. The order is back to the agreement step.':
            'Đã hủy đơn đặt hàng. Đơn quay lại bước thỏa thuận.',
        'Order confirmation cancelled. Later steps already happened, so the order status was left as it is.':
            'Đã hủy đơn đặt hàng. Các bước sau đã diễn ra nên trạng thái đơn được giữ nguyên.',
        'Error cancelling order confirmation':
            'Lỗi khi hủy đơn đặt hàng',
        'No advance was received - this step was waived.':
            'Không nhận tạm ứng — bước này đã được bỏ qua.',
        'Order progress':
            'Tiến độ đơn hàng',
        'Your text was restored. Please choose any images again.':
            'Nội dung bạn nhập đã được khôi phục. Vui lòng chọn lại ảnh (nếu có).',
        'Vui lòng chọn vật tư và nhập số lượng lớn hơn 0':
            'Vui lòng chọn vật tư và nhập số lượng lớn hơn 0',

        # -- Document lifecycle --
        'Current version':          'Bản hiện hành',
        'Replaced':                 'Đã thay thế',

        # -- Customer debt report --
        'Customer Debt':
            'Công nợ khách hàng',
        'Total still owed to us':
            'Tổng còn phải thu',
        'Customers with an unpaid balance':
            'Khách còn dư nợ',
        'Still owing':
            'Còn nợ',
        'Agreed value':
            'Giá trị đã chốt',
        'Still owed':
            'Còn phải thu',
        'Paid in full':
            'Đã thanh toán đủ',
        'No customer has an outstanding balance.':
            'Không có khách hàng nào còn dư nợ.',
        'Largest debt first. Only confirmed payments count as received — money promised but not yet confirmed still shows as owed.':
            'Nợ lớn nhất xếp trước. Chỉ khoản thanh toán đã xác nhận mới tính là đã thu — tiền mới hứa nhưng chưa xác nhận vẫn hiện là còn nợ.',

        # -- Job costing --
        'Job cost so far':
            'Chi phí đơn hàng đến hiện tại',
        'Materials issued':
            'Vật tư đã cấp phát',
        'Difference':
            'Chênh lệch',
        'Incomplete':
            'Chưa đủ dữ liệu',
        '%(n)s material(s) issued to this job have no cost recorded yet, so the figure above is lower than the real cost. A cost is set the first time that material is received with a price on the purchase order.':
            'Có %(n)s vật tư đã cấp phát cho đơn này chưa có giá vốn, nên con số trên đang thấp hơn chi phí thật. Giá vốn được ghi nhận lần đầu khi vật tư đó được nhập kho kèm đơn giá trên đơn mua.',
        'Materials only — labour is not recorded in the system, so this is not the final profit.':
            'Mới tính vật tư — hệ thống chưa ghi nhận công thợ, nên đây chưa phải lợi nhuận cuối cùng.',
    }
}


def t(key: str, lang: str = None) -> str:
    """Translate a UI string.

    In English mode the key itself is returned unchanged.
    In Vietnamese mode the Vietnamese translation is returned, or the key
    if no translation is registered.
    """
    if lang is None:
        try:
            from flask import session, has_request_context
            if has_request_context():
                lang = session.get('lang', 'vi')
            else:
                lang = 'vi'
        except Exception:
            lang = 'vi'
            
    if lang == 'en':
        return key
    return TRANSLATIONS.get(lang, {}).get(key, key)


# --- Supplementary Vietnamese translations (full-coverage pass) ---
TRANSLATIONS['vi'].update({'(overall)': '(chung)', 'Account Holder': 'Chủ tài khoản', 'Account Number': 'Số tài khoản', 'Add Supplier': 'Thêm nhà cung cấp', 'Add material': 'Thêm vật tư', 'Additional Info': 'Thông tin bổ sung', 'Additional Information': 'Thông tin bổ sung', 'Address or location': 'Địa chỉ / nơi chốn', 'Alert when total stock falls below this level': 'Cảnh báo khi tổng tồn kho xuống dưới mức này', 'All materials are above their minimum stock level.': 'Tất cả vật tư đều trên mức tồn tối thiểu.', 'Amount in Words:': 'Số tiền bằng chữ:', 'Are you sure you want to delete': 'Bạn có chắc muốn xóa', 'Bank': 'Ngân hàng', 'Bank Account Info:': 'Thông tin tài khoản ngân hàng:', 'Business Registration No.': 'Số ĐKKD/GPKD', 'Cancellation Notice (days)': 'Số ngày báo trước khi hủy', 'Cancellation Notice:': 'Báo trước khi hủy:', 'Certifications': 'Chứng nhận', 'Composition': 'Thành phần', 'Composition & Appearance': 'Thành phần & Ngoại quan', 'Configure up to 10 custom fields per document type. Enabled fields appear on the create form.': 'Cấu hình tối đa 10 trường tùy chỉnh cho mỗi loại chứng từ. Trường được bật sẽ hiện trên biểu mẫu tạo.', 'Contact': 'Liên hệ', 'Contact Person': 'Người liên hệ', 'Contract Content': 'Nội dung hợp đồng', 'Contract Date': 'Ngày hợp đồng', 'Contract Start Date': 'Ngày bắt đầu hợp đồng', 'Contract Status': 'Trạng thái hợp đồng', 'Country of Origin': 'Xuất xứ', 'Data Type': 'Kiểu dữ liệu', 'Days to Complete': 'Số ngày hoàn thành', 'Days to Complete:': 'Số ngày hoàn thành:', 'Deactivate this supplier?': 'Ngừng hoạt động nhà cung cấp này?', 'Delete Document': 'Xóa tài liệu', 'Delete this material line?': 'Xóa dòng vật tư này?', 'Dimensions & Weight': 'Kích thước & Trọng lượng', 'Document Type': 'Loại tài liệu', 'Durability': 'Độ bền', 'Durability (Martindale)': 'Độ bền (Martindale)', 'Edit Supplier': 'Sửa nhà cung cấp', 'Extension Fields': 'Trường mở rộng', 'Field': 'Trường', 'Filename': 'Tên tệp', 'Finish': 'Hoàn thiện bề mặt', 'Fire Resistance': 'Chống cháy', 'Foam Density': 'Mật độ mút', 'Foam Density (kg/m³)': 'Mật độ mút (kg/m³)', 'For item': 'Cho hạng mục', 'Handover Date *': 'Ngày bàn giao *', 'Handover Time': 'Thời gian bàn giao', 'Hardness': 'Độ cứng', 'Hardness / Grade': 'Độ cứng / Cấp', 'Image': 'Hình ảnh', 'In stock': 'Tồn kho', 'Issued': 'Đã cấp', 'Items to produce': 'Hạng mục cần sản xuất', 'Label': 'Nhãn', 'Lead Time': 'Thời gian giao hàng', 'Lead Time (days)': 'Thời gian giao (ngày)', 'Low Stock Materials': 'Vật tư tồn thấp', 'Manage supplier records. Assign suppliers when creating materials.': 'Quản lý nhà cung cấp. Gán nhà cung cấp khi tạo vật tư.', 'Manage suppliers': 'Quản lý nhà cung cấp', 'Materials needed': 'Vật tư cần dùng', 'Min level': 'Mức tối thiểu', 'Name of contact': 'Tên người liên hệ', 'No items recorded.': 'Chưa có hạng mục nào.', 'No materials yet. Add materials below or save/apply a norm.': 'Chưa có vật tư. Thêm bên dưới hoặc lưu/áp dụng định mức.', 'No supplier': 'Không có nhà cung cấp', 'No supplier assigned.': 'Chưa gán nhà cung cấp.', 'No suppliers yet. Add one to get started.': 'Chưa có nhà cung cấp. Thêm mới để bắt đầu.', 'None': 'Không có', 'On': 'Bật', 'Order': 'Đơn hàng', 'Origin & Compliance': 'Xuất xứ & Tuân thủ', 'Pattern': 'Họa tiết', 'Payment Bank Account': 'Tài khoản ngân hàng nhận thanh toán', 'Payment Bank:': 'Ngân hàng thanh toán:', 'Payment Type': 'Loại thanh toán', 'Product / Work': 'Sản phẩm / Công việc', 'Production Plan': 'Kế hoạch sản xuất', 'Quality & Performance': 'Chất lượng & Hiệu năng', 'Quotation Ref. Date:': 'Ngày báo giá tham chiếu:', 'Rating': 'Đánh giá', 'Reason': 'Lý do', 'Reference Contract:': 'Hợp đồng tham chiếu:', 'Referenced Contract': 'Hợp đồng tham chiếu', 'Remaining Balance:': 'Còn lại phải trả:', 'Required': 'Bắt buộc', 'Roll Length': 'Chiều dài cuộn', 'Roll Length (m)': 'Chiều dài cuộn (m)', 'Save as norm': 'Lưu định mức', 'Save material list of this item as a reusable norm?': 'Lưu danh sách vật tư của hạng mục này thành định mức để dùng lại?', 'Save norm': 'Lưu định mức', 'Select a material': 'Chọn vật tư', 'Settings': 'Cài đặt', 'Signing Date *': 'Ngày ký *', 'Signing Date:': 'Ngày ký:', 'Start Date:': 'Ngày bắt đầu:', 'Subtotal': 'Cộng tiền hàng', 'Supplier': 'Nhà cung cấp', 'Supplier product code': 'Mã sản phẩm bên NCC', "Supplier's SKU": 'Mã SKU của NCC', 'Suppliers': 'Nhà cung cấp', 'The production plan is created automatically once the contract is signed.': 'Kế hoạch sản xuất được tạo tự động sau khi hợp đồng được ký.', 'Thickness': 'Độ dày', 'Thickness (mm)': 'Độ dày (mm)', 'This action cannot be undone. The file will be permanently removed.': 'Hành động này không thể hoàn tác. Tệp sẽ bị xóa vĩnh viễn.', 'UV Resistance': 'Kháng tia UV', 'Update': 'Cập nhật', 'Water Resistance': 'Kháng nước', 'Website': 'Website', 'Weight / Unit': 'Trọng lượng / Đơn vị', 'Weight/Unit': 'Trọng lượng/Đơn vị', 'Width': 'Khổ rộng', 'Width (cm)': 'Khổ rộng (cm)', 'Work Completion Summary:': 'Tóm tắt công việc hoàn thành:', 'days': 'ngày', 'e.g. 100% Polyester, Da bò thật Grade A': 'vd: 100% Polyester, Da bò thật Grade A', 'e.g. Công ty TNHH Vải Thiên Hà': 'vd: Công ty TNHH Vải Thiên Hà', 'e.g. Mét vuông - dùng cho vải và da': 'vd: Mét vuông - dùng cho vải và da', 'e.g. PO Number': 'vd: Số PO', 'e.g. Vải bọc': 'vd: Vải bọc', 'from contract — read-only': 'lấy từ hợp đồng — chỉ đọc', 'Purchase Suggestions': 'Đề xuất mua hàng', 'Low Stock': 'Tồn kho thấp', 'Code': 'Mã', 'Name': 'Tên', 'items': 'sản phẩm', 'Deactivate this user?': 'Vô hiệu hóa người dùng này?', 'Deactivate this store?': 'Vô hiệu hóa cửa hàng này?', 'Purchase Orders': 'Đơn mua hàng', 'Notes': 'Ghi chú', 'Quotation': 'Báo giá', 'Contract': 'Hợp đồng', 'Handover': 'Bàn giao', 'Payment': 'Thanh toán', 'Purchase_order': 'Đơn mua hàng', 'Goods_receipt': 'Phiếu nhập kho', 'Purchase Requisitions': 'Đề nghị mua hàng', 'Goods Receipts': 'Phiếu nhập kho', 'Purchase_requisition': 'Đề nghị mua hàng', 'Inventory': 'Kho & Vật tư', 'Purchasing': 'Mua hàng', 'Administration': 'Quản trị', 'Latest': 'Mới nhất'})


# --- Vietnamese for the keys the widened i18n lint found: framework
# agreements, supplier invoices, the workflow + standardization settings
# screens, and the order/contract edit forms. ---
TRANSLATIONS['vi'].update({
    '3-way match': 'Đối chiếu 3 chiều',
    'A framework agreement sets the general terms of cooperation. It does not carry quantity, price or delivery date for any single order, so each order still needs its own Order Confirmation (Đơn đặt hàng) as the basis for a VAT invoice.': 'Hợp đồng nguyên tắc quy định các điều khoản hợp tác chung. Hợp đồng này không có số lượng, đơn giá hay ngày giao cho từng đơn cụ thể, nên mỗi đơn vẫn cần Đơn đặt hàng riêng làm căn cứ xuất hóa đơn GTGT.',
    'A revision closes the previous line instead of overwriting it, so past orders keep their price.': 'Bản sửa đổi sẽ đóng dòng giá cũ thay vì ghi đè, nhờ đó các đơn hàng cũ vẫn giữ nguyên giá.',
    'Add price': 'Thêm giá',
    'Advance Skipped': 'Bỏ qua tạm ứng',
    'Agreed Price': 'Giá thỏa thuận',
    'Agreed Price List': 'Bảng giá thỏa thuận',
    'Agreement Number': 'Số hợp đồng nguyên tắc',
    'Agreements': 'Hợp đồng nguyên tắc',
    'Already invoiced': 'Đã xuất hóa đơn',
    'Amounts': 'Số tiền',
    'Auto-renew': 'Tự động gia hạn',
    'Bank transfer': 'Chuyển khoản',
    'Capped at 8% of the value of the breached obligation (Điều 301 Luật Thương mại 2005)': 'Tối đa 8% giá trị phần nghĩa vụ bị vi phạm (Điều 301 Luật Thương mại 2005)',
    'Cash payment — check input-VAT deductibility': 'Thanh toán tiền mặt — lưu ý điều kiện khấu trừ thuế GTGT đầu vào',
    'Changing these rules affects new actions only. Documents already created keep their history.': 'Thay đổi quy tắc chỉ áp dụng cho các thao tác mới. Chứng từ đã tạo vẫn giữ nguyên lịch sử.',
    'Commercial terms': 'Điều khoản thương mại',
    'Confirm Invoice': 'Xác nhận hóa đơn',
    'Covered by framework agreement': 'Thuộc hợp đồng nguyên tắc',
    'Current': 'Hiện hành',
    'Customer representative': 'Đại diện khách hàng',
    'Data Standardization': 'Chuẩn hóa dữ liệu',
    'Delivery Terms': 'Điều khoản giao hàng',
    'Discount %': 'Chiết khấu %',
    'Dispute Resolution': 'Giải quyết tranh chấp',
    'Each row is one prerequisite of one step. Change how strictly it is enforced:': 'Mỗi dòng là một điều kiện tiên quyết của một bước. Chọn mức độ ràng buộc:',
    'Edit Framework Agreement': 'Sửa hợp đồng nguyên tắc',
    'Edit Order': 'Sửa đơn hàng',
    'Effective From': 'Hiệu lực từ',
    'Effective To': 'Hiệu lực đến',
    'Enforcement': 'Mức ràng buộc',
    'Enter the invoice exactly as the supplier issued it. The quantities are checked against what was ordered and what was actually received — a mismatch is flagged for review, not blocked.': 'Nhập hóa đơn đúng như nhà cung cấp đã phát hành. Số lượng sẽ được đối chiếu với số đã đặt và số thực nhận — nếu lệch sẽ được cảnh báo để rà soát, không bị chặn.',
    'Framework Agreements': 'Hợp đồng nguyên tắc',
    'From': 'Từ',
    'Identifiers (tax codes, bank accounts, document numbers, emails, phone numbers) are never standardized, whatever is configured here — changing them would corrupt a legal value or hide a typing error that should be corrected instead.': 'Các định danh (mã số thuế, số tài khoản, số chứng từ, email, số điện thoại) không bao giờ bị chuẩn hóa, dù cấu hình thế nào — sửa chúng sẽ làm sai giá trị pháp lý hoặc che mất lỗi nhập liệu cần được sửa đúng.',
    'Invoice': 'Hóa đơn',
    'Invoice Date': 'Ngày hóa đơn',
    'Invoice Number': 'Số hóa đơn',
    'Invoice details': 'Chi tiết hóa đơn',
    'Invoice qty': 'SL hóa đơn',
    'Invoiced lines': 'Dòng đã xuất hóa đơn',
    'Issue Order Confirmation': 'Lập đơn đặt hàng',
    'Leave empty for open-ended (vô thời hạn)': 'Để trống nếu vô thời hạn',
    'Leave empty for the default message': 'Để trống để dùng thông báo mặc định',
    'Line total': 'Thành tiền',
    'Match': 'Khớp',
    'Matching discrepancy': 'Sai lệch khi đối chiếu',
    'Message shown when blocked': 'Thông báo hiển thị khi bị chặn',
    'Method': 'Hình thức',
    'Mode': 'Chế độ',
    'New Framework Agreement': 'Tạo hợp đồng nguyên tắc',
    'Ngày bắt đầu thực hiện hợp đồng': 'Ngày bắt đầu thực hiện hợp đồng',
    'Ngân hàng thanh toán cho hợp đồng này:': 'Ngân hàng thanh toán cho hợp đồng này:',
    'No agreed prices yet. Orders will use their quoted prices.': 'Chưa có giá thỏa thuận. Đơn hàng sẽ dùng giá trên báo giá.',
    'No new orders may cite this agreement while it is suspended.': 'Không được tạo đơn hàng mới theo hợp đồng này trong thời gian tạm ngưng.',
    'No orders have been issued under this agreement yet.': 'Chưa có đơn hàng nào phát sinh theo hợp đồng này.',
    'Number': 'Số',
    'Nội dung lấy từ mô tả đơn hàng – chỉnh sửa trong trang Order': 'Nội dung lấy từ mô tả đơn hàng – chỉnh sửa trong trang Order',
    'OK': 'Đồng ý',
    'Only the description fields can be changed here. The customer, store and amounts come from the order documents and are not editable.': 'Chỉ sửa được các trường mô tả tại đây. Khách hàng, cửa hàng và số tiền lấy từ chứng từ của đơn hàng nên không sửa được.',
    'Open-ended': 'Vô thời hạn',
    'Order Confirmation': 'Đơn đặt hàng',
    'Order Workflow': 'Quy trình đơn hàng',
    'Ordered': 'Đã đặt',
    'Orders under this agreement': 'Đơn hàng theo hợp đồng này',
    'Our representative': 'Đại diện bên chúng tôi',
    'Paid': 'Đã thanh toán',
    'Parties and validity': 'Các bên và hiệu lực',
    'Payment No.': 'Số phiếu thanh toán',
    'Payments': 'Thanh toán',
    'Penalty %': 'Phạt vi phạm %',
    'Preview sample text': 'Xem thử với văn bản mẫu',
    'Product': 'Sản phẩm',
    'Protected identifier — never standardized': 'Định danh được bảo vệ — không bao giờ chuẩn hóa',
    'Quality Terms': 'Điều khoản chất lượng',
    'Quantities default to what is received but not yet invoiced. Leave a line at 0 to exclude it.': 'Số lượng mặc định là phần đã nhận nhưng chưa xuất hóa đơn. Để 0 nếu muốn loại dòng đó.',
    'Reason (for suspend / terminate)': 'Lý do (tạm ngưng / chấm dứt)',
    'Record': 'Ghi nhận',
    'Record Payment': 'Ghi nhận thanh toán',
    'Record Supplier Invoice': 'Ghi nhận hóa đơn nhà cung cấp',
    'Reference': 'Tham chiếu',
    'Renewal Notice (days)': 'Số ngày báo trước gia hạn',
    'Requires': 'Yêu cầu',
    'Reset': 'Đặt lại',
    'Reset all standardization rules to the defaults?': 'Đặt lại toàn bộ quy tắc chuẩn hóa về mặc định?',
    'Reset all workflow rules to the standard process?': 'Đặt lại toàn bộ quy tắc quy trình về quy trình chuẩn?',
    'Reset to defaults': 'Đặt lại về mặc định',
    'Reset to standard process': 'Đặt lại về quy trình chuẩn',
    'Scope of cooperation': 'Phạm vi hợp tác',
    'Seller Tax Code': 'Mã số thuế bên bán',
    'Series': 'Ký hiệu',
    'Signatories': 'Người ký',
    'Signed Date': 'Ngày ký',
    'Step': 'Bước',
    'Supplier Invoices': 'Hóa đơn nhà cung cấp',
    'Suspend': 'Tạm ngưng',
    'Số ngày báo trước nếu muốn hủy HĐ': 'Số ngày báo trước nếu muốn hủy HĐ',
    'Số ngày cam kết hoàn thiện': 'Số ngày cam kết hoàn thiện',
    'Số tiền bằng chữ': 'Số tiền bằng chữ',
    'Terminate': 'Chấm dứt',
    'Terminate this agreement? Orders already issued keep their validity.': 'Chấm dứt hợp đồng nguyên tắc này? Các đơn hàng đã phát sinh vẫn giữ nguyên hiệu lực.',
    'This is a warning, not a block — review it before paying.': 'Đây là cảnh báo, không phải chặn — hãy rà soát trước khi thanh toán.',
    'Tidies what users type so documents come out consistent. Each row is one field; the transforms run in the order listed.': 'Chuẩn hóa nội dung người dùng nhập để chứng từ in ra đồng nhất. Mỗi dòng là một trường; các phép biến đổi chạy theo thứ tự liệt kê.',
    'To': 'Đến',
    'Transforms': 'Phép chuẩn hóa',
    'Transforms marked with an asterisk change meaning, not just formatting — review the preview before enabling them automatically.': 'Các phép có dấu sao làm thay đổi nội dung chứ không chỉ định dạng — hãy xem thử trước khi bật tự động.',
    'Unit price': 'Đơn giá',
    'VAT': 'Thuế GTGT',
    'VAT %': 'Thuế GTGT %',
    'Yes': 'Có',
    'applied silently when the record is saved': 'tự áp dụng khi lưu, không hỏi lại',
    'auto': 'tự động',
    'can be skipped, but only with a reason that is recorded': 'được phép bỏ qua, nhưng phải ghi lý do',
    'confirm': 'hỏi xác nhận',
    'or Discount %': 'hoặc Chiết khấu %',
    'shown as a warning only, never blocks': 'chỉ hiện cảnh báo, không chặn',
    'suggested only — the value is never rewritten without a person agreeing': 'chỉ gợi ý — giá trị không bị sửa nếu người dùng chưa đồng ý',
    'the step is blocked until the prerequisite is met': 'bước này bị chặn cho đến khi đáp ứng điều kiện tiên quyết',
})


# --- Names for the icon-only row actions (tooltip + screen reader). ---
TRANSLATIONS['vi'].update({
    'Remove this row': 'Xóa dòng này',
    'Remove this bank account': 'Xóa tài khoản ngân hàng này',
    'Delete this file': 'Xóa tệp này',
    'Adjust stock': 'Điều chỉnh tồn kho',
})

TRANSLATIONS['vi'].update({'Áp dụng quy tắc này': 'Áp dụng quy tắc này'})

# --- Messages that carry a value, so the key holds a placeholder rather than
# --- being built with an f-string (which would be a new key every call). ---
TRANSLATIONS['vi'].update({
    'Không lưu được: %(message)s': 'Không lưu được: %(message)s',
    'Không hủy được biên bản bàn giao: %(message)s':
        'Không hủy được biên bản bàn giao: %(message)s',
    'Không hủy được phiếu thanh toán: %(message)s':
        'Không hủy được phiếu thanh toán: %(message)s',
    'Không tạo được tài liệu: %(message)s': 'Không tạo được tài liệu: %(message)s',
    'Không thể bỏ qua tạm ứng: %(message)s': 'Không thể bỏ qua tạm ứng: %(message)s',
    'Số báo giá "%(number)s" đã được dùng. Vui lòng chọn số khác.':
        'Số báo giá "%(number)s" đã được dùng. Vui lòng chọn số khác.',
    'Số hợp đồng "%(number)s" đã được dùng. Vui lòng chọn số khác.':
        'Số hợp đồng "%(number)s" đã được dùng. Vui lòng chọn số khác.',
    'Số biên bản bàn giao "%(number)s" đã được dùng. Vui lòng chọn số khác.':
        'Số biên bản bàn giao "%(number)s" đã được dùng. Vui lòng chọn số khác.',
    'Số phiếu thanh toán "%(number)s" đã được dùng. Vui lòng chọn số khác.':
        'Số phiếu thanh toán "%(number)s" đã được dùng. Vui lòng chọn số khác.',
    'Không đủ tồn kho — chưa trừ kho. Còn thiếu: %(detail)s':
        'Không đủ tồn kho — chưa trừ kho. Còn thiếu: %(detail)s',
    ' … và %(n)d vật tư khác': ' … và %(n)d vật tư khác',
})

TRANSLATIONS['vi'].update({
    'Mẫu "%(name)s" đã được tải lên thành công.': 'Mẫu "%(name)s" đã được tải lên thành công.',
    'Mẫu "%(name)s" đã được vô hiệu hóa.': 'Mẫu "%(name)s" đã được vô hiệu hóa.',
    'Mẫu "%(name)s" đã được kích hoạt, thay cho: %(replaced)s.': 'Mẫu "%(name)s" đã được kích hoạt, thay cho: %(replaced)s.',
    'Mẫu "%(name)s" đã được kích hoạt.': 'Mẫu "%(name)s" đã được kích hoạt.',
    'Cửa hàng "%(name)s" đã bị vô hiệu hóa': 'Cửa hàng "%(name)s" đã bị vô hiệu hóa',
    'Tài khoản "%(name)s" đã bị vô hiệu hóa': 'Tài khoản "%(name)s" đã bị vô hiệu hóa',
    'Nguyên vật liệu "%(name)s" đã được tạo': 'Nguyên vật liệu "%(name)s" đã được tạo',
    'NVL "%(name)s" đã bị vô hiệu hóa': 'NVL "%(name)s" đã bị vô hiệu hóa',
    'Mã công ty "%(code)s" đã tồn tại.': 'Mã công ty "%(code)s" đã tồn tại.',
    'Công ty "%(name)s" (%(code)s) đã được tạo thành công.': 'Công ty "%(name)s" (%(code)s) đã được tạo thành công.',
    'Công ty "%(name)s" đã được %(state)s.': 'Công ty "%(name)s" đã được %(state)s.',
    'Tên đăng nhập "%(username)s" đã tồn tại.': 'Tên đăng nhập "%(username)s" đã tồn tại.',
    'Master admin "%(username)s" đã được tạo.': 'Master admin "%(username)s" đã được tạo.',
    'Không thực hiện được. Vui lòng thử lại.': 'Không thực hiện được. Vui lòng thử lại.',
})

TRANSLATIONS['vi'].update({
    'Status': 'Trạng thái',
    'Chưa bàn giao': 'Chưa bàn giao',
    'Chưa thanh toán đủ': 'Chưa thanh toán đủ',
    'Đang thực hiện': 'Đang thực hiện',
    'Đã hoàn thành': 'Đã hoàn thành',
    'Đã hủy': 'Đã hủy',
    'Tìm theo mã đơn, tên công việc, khách hàng hoặc số chứng từ...':
        'Tìm theo mã đơn, tên công việc, khách hàng hoặc số chứng từ...',
})

TRANSLATIONS['vi'].update({
    'Production': 'Sản xuất',
    'Production Plans': 'Kế hoạch sản xuất',
    'Đang sản xuất': 'Đang sản xuất',
    'Đang bị chậm': 'Đang bị chậm',
    'Nháp': 'Nháp',
    'Đã xong': 'Đã xong',
    'Đã nghiệm thu': 'Đã nghiệm thu',
    'Kế hoạch sản xuất được tạo tự động sau khi hợp đồng được ký. Các kế hoạch bị chậm luôn nằm ở đầu danh sách.':
        'Kế hoạch sản xuất được tạo tự động sau khi hợp đồng được ký. Các kế hoạch bị chậm luôn nằm ở đầu danh sách.',
    'Chưa có kế hoạch sản xuất nào. Kế hoạch được tạo tự động khi hợp đồng được ký.':
        'Chưa có kế hoạch sản xuất nào. Kế hoạch được tạo tự động khi hợp đồng được ký.',
})

TRANSLATIONS['vi'].update({'Tồn kho': 'Tồn kho', 'thiếu': 'thiếu'})

TRANSLATIONS['vi'].update({
    'Chờ xác nhận': 'Chờ xác nhận',
    'Date': 'Ngày',
    'Amount': 'Số tiền',
    'Các phiếu thanh toán đã ghi nhận nhưng chưa được xác nhận. Cho đến khi xác nhận, số tiền này vẫn bị tính là khách còn nợ.':
        'Các phiếu thanh toán đã ghi nhận nhưng chưa được xác nhận. Cho đến khi xác nhận, số tiền này vẫn bị tính là khách còn nợ.',
    'Phiếu cũ nhất ở trên: để càng lâu thì càng dễ bị bỏ quên vì ai cũng tưởng người khác đã xử lý.':
        'Phiếu cũ nhất ở trên: để càng lâu thì càng dễ bị bỏ quên vì ai cũng tưởng người khác đã xử lý.',
})


# --- Vietnamese for the messages composed in Python: every save
# confirmation and every rejection. Keys already written in Vietnamese
# self-map — they render correctly today, and registering them keeps the
# lint honest and gives English mode something to fall back from. ---
TRANSLATIONS['vi'].update({
    'A canceled order cannot be edited': 'Đơn hàng đã hủy thì không sửa được',
    'Advance payment can only be recorded after contract is signed': 'Chỉ ghi nhận tạm ứng sau khi hợp đồng đã được ký',
    'Advance payment skipped by agreement with the customer': 'Đã bỏ qua tạm ứng theo thỏa thuận với khách hàng',
    'Advance payment step already completed': 'Bước tạm ứng đã hoàn tất',
    'Agreement number already exists': 'Số hợp đồng nguyên tắc đã tồn tại',
    'Agreement number is required': 'Vui lòng nhập số hợp đồng nguyên tắc',
    'All fields are required': 'Vui lòng điền đầy đủ các trường',
    'An approved quotation is needed to issue an order confirmation': 'Cần có báo giá đã duyệt mới lập được đơn đặt hàng',
    'Cancellation reason is required': 'Vui lòng nhập lý do hủy',
    'Cannot edit a signed contract': 'Không sửa được hợp đồng đã ký',
    'Chưa có cửa hàng nào. Vui lòng tạo cửa hàng trước.': 'Chưa có cửa hàng nào. Vui lòng tạo cửa hàng trước.',
    'Chỉ cho phép tệp .docx, .rtf hoặc .txt.': 'Chỉ cho phép tệp .docx, .rtf hoặc .txt.',
    'Chỉ cấp phát vật tư sau khi kế hoạch đã được duyệt (chốt).': 'Chỉ cấp phát vật tư sau khi kế hoạch đã được duyệt (chốt).',
    'Company not found': 'Không tìm thấy công ty',
    'Company registered successfully. Please login.': 'Đăng ký công ty thành công. Vui lòng đăng nhập.',
    'Company settings updated successfully': 'Đã cập nhật thông tin công ty',
    'Contract cannot be canceled': 'Không hủy được hợp đồng này',
    'Contract created successfully': 'Đã tạo hợp đồng',
    'Contract has been canceled successfully': 'Đã hủy hợp đồng',
    'Contract marked as signed': 'Đã đánh dấu hợp đồng là đã ký',
    'Contract must be signed before skipping advance payment': 'Phải ký hợp đồng trước khi bỏ qua tạm ứng',
    'Contract not found': 'Không tìm thấy hợp đồng',
    'Contract not found or access denied': 'Không tìm thấy hợp đồng hoặc không có quyền truy cập',
    'Contract updated successfully': 'Đã cập nhật hợp đồng',
    'Customer created successfully': 'Đã tạo khách hàng',
    'Customer not found or access denied': 'Không tìm thấy khách hàng hoặc không có quyền truy cập',
    'Cập nhật cửa hàng thành công': 'Cập nhật cửa hàng thành công',
    'Cập nhật người dùng thành công': 'Cập nhật người dùng thành công',
    'Cập nhật thông tin khách hàng thành công!': 'Cập nhật thông tin khách hàng thành công!',
    'Cập nhật tồn kho thành công': 'Cập nhật tồn kho thành công',
    'Cửa hàng không tìm thấy': 'Cửa hàng không tìm thấy',
    'Danh mục đã bị vô hiệu hóa': 'Danh mục đã bị vô hiệu hóa',
    'Danh mục đã được cập nhật': 'Danh mục đã được cập nhật',
    'Danh mục đã được tạo': 'Danh mục đã được tạo',
    'Document deleted successfully': 'Đã xóa tài liệu',
    'Document file not found': 'Không tìm thấy tệp tài liệu',
    'Document not found or access denied': 'Không tìm thấy tài liệu hoặc không có quyền truy cập',
    'Effective from date is required': 'Vui lòng nhập ngày bắt đầu hiệu lực',
    'Enter either an agreed price or a discount': 'Nhập giá thỏa thuận hoặc mức chiết khấu',
    'Error adding price line': 'Không thêm được dòng giá',
    'Error approving quotation': 'Không duyệt được báo giá',
    'Error canceling contract': 'Không hủy được hợp đồng',
    'Error canceling order': 'Không hủy được đơn hàng',
    'Error canceling quotation': 'Không hủy được báo giá',
    'Error confirming handover': 'Không xác nhận được biên bản bàn giao',
    'Error confirming payment': 'Không xác nhận được thanh toán',
    'Error creating contract': 'Không tạo được hợp đồng',
    'Error creating customer': 'Không tạo được khách hàng',
    'Error creating framework agreement': 'Không tạo được hợp đồng nguyên tắc',
    'Error creating handover record': 'Không tạo được biên bản bàn giao',
    'Error creating order': 'Không tạo được đơn hàng',
    'Error creating payment report': 'Không tạo được phiếu thanh toán',
    'Error creating quotation': 'Không tạo được báo giá',
    'Error deleting document': 'Không xóa được tài liệu',
    'Error downloading document': 'Không tải được tài liệu',
    'Error issuing order confirmation': 'Không lập được đơn đặt hàng',
    'Error recording payment': 'Không ghi nhận được thanh toán',
    'Error recording supplier invoice': 'Không ghi nhận được hóa đơn nhà cung cấp',
    'Error signing contract': 'Không ký được hợp đồng',
    'Error updating company settings': 'Không cập nhật được thông tin công ty',
    'Error updating contract': 'Không cập nhật được hợp đồng',
    'Error updating framework agreement': 'Không cập nhật được hợp đồng nguyên tắc',
    'Error updating handover record': 'Không cập nhật được biên bản bàn giao',
    'Error updating order': 'Không cập nhật được đơn hàng',
    'Error updating payment report': 'Không cập nhật được phiếu thanh toán',
    'Error updating quotation': 'Không cập nhật được báo giá',
    'Final payment can only be recorded after handover is confirmed': 'Chỉ ghi nhận thanh toán cuối sau khi biên bản bàn giao đã được xác nhận',
    'Framework agreement activated': 'Đã kích hoạt hợp đồng nguyên tắc',
    'Framework agreement created': 'Đã tạo hợp đồng nguyên tắc',
    'Framework agreement not found or access denied': 'Không tìm thấy hợp đồng nguyên tắc hoặc không có quyền truy cập',
    'Framework agreement suspended — no new orders can cite it': 'Đã tạm ngưng hợp đồng nguyên tắc — không đơn hàng mới nào được viện dẫn',
    'Framework agreement terminated': 'Đã chấm dứt hợp đồng nguyên tắc',
    'Framework agreement updated': 'Đã cập nhật hợp đồng nguyên tắc',
    'Handover record canceled successfully': 'Đã hủy biên bản bàn giao',
    'Handover record cannot be edited (already confirmed or canceled)': 'Không sửa được biên bản bàn giao (đã xác nhận hoặc đã hủy)',
    'Handover record confirmed': 'Đã xác nhận biên bản bàn giao',
    'Handover record created successfully': 'Đã tạo biên bản bàn giao',
    'Handover record not found': 'Không tìm thấy biên bản bàn giao',
    'Handover record not found or access denied': 'Không tìm thấy biên bản bàn giao hoặc không có quyền truy cập',
    'Handover record updated successfully': 'Đã cập nhật biên bản bàn giao',
    'Hạng mục này chưa khai vật tư nên chưa có định mức để lưu': 'Hạng mục này chưa khai vật tư nên chưa có định mức để lưu',
    'Invalid customer selection': 'Khách hàng đã chọn không hợp lệ',
    'Invalid email or password': 'Email hoặc mật khẩu không đúng',
    'Invalid store ID': 'Mã cửa hàng không hợp lệ',
    'Invoice recorded with a matching discrepancy: ': 'Đã ghi nhận hóa đơn nhưng có sai lệch khi đối chiếu: ',
    'Không có quyền thiết lập vai trò Quản Trị Công Ty': 'Không có quyền thiết lập vai trò Quản Trị Công Ty',
    'Không có quyền truy cập cửa hàng này': 'Không có quyền truy cập cửa hàng này',
    'Không có quyền tạo tài khoản Quản Trị Công Ty': 'Không có quyền tạo tài khoản Quản Trị Công Ty',
    'Không có vật tư cần mua để tạo đơn.': 'Không có vật tư cần mua để tạo đơn.',
    'Không hủy được biên bản bàn giao. Vui lòng thử lại.': 'Không hủy được biên bản bàn giao. Vui lòng thử lại.',
    'Không hủy được phiếu thanh toán. Vui lòng thử lại.': 'Không hủy được phiếu thanh toán. Vui lòng thử lại.',
    'Không thể vô hiệu hóa tài khoản của chính mình': 'Không thể vô hiệu hóa tài khoản của chính mình',
    'Không tìm thấy công ty.': 'Không tìm thấy công ty.',
    'Không tìm thấy hạng mục trong kế hoạch này': 'Không tìm thấy hạng mục trong kế hoạch này',
    'Không tìm thấy khách hàng hoặc không có quyền truy cập': 'Không tìm thấy khách hàng hoặc không có quyền truy cập',
    'Không tìm thấy kế hoạch hoặc không có quyền': 'Không tìm thấy kế hoạch hoặc không có quyền',
    'Không tìm thấy mẫu.': 'Không tìm thấy mẫu.',
    'Không tìm thấy phiếu nhập kho hoặc không có quyền truy cập': 'Không tìm thấy phiếu nhập kho hoặc không có quyền truy cập',
    'Không tìm thấy đơn mua hoặc không có quyền': 'Không tìm thấy đơn mua hoặc không có quyền',
    'Không tìm thấy đơn mua hoặc không có quyền truy cập': 'Không tìm thấy đơn mua hoặc không có quyền truy cập',
    'Không tìm thấy đề nghị mua hàng hoặc không có quyền truy cập': 'Không tìm thấy đề nghị mua hàng hoặc không có quyền truy cập',
    'Không tạo được tài liệu. Vui lòng kiểm tra mẫu và thử lại.': 'Không tạo được tài liệu. Vui lòng kiểm tra mẫu và thử lại.',
    'Không tải lên được mẫu. Vui lòng kiểm tra tệp và thử lại.': 'Không tải lên được mẫu. Vui lòng kiểm tra tệp và thử lại.',
    'Kế hoạch đã chốt (đã duyệt) — không thể sửa danh mục vật tư.': 'Kế hoạch đã chốt (đã duyệt) — không thể sửa danh mục vật tư.',
    'Login failed. Please try again.': 'Đăng nhập không thành công. Vui lòng thử lại.',
    'Lỗi hệ thống': 'Lỗi hệ thống',
    'Lỗi hệ thống khi cập nhật NVL': 'Lỗi hệ thống khi cập nhật NVL',
    'Lỗi hệ thống khi cập nhật tồn kho': 'Lỗi hệ thống khi cập nhật tồn kho',
    'Lỗi hệ thống khi tạo NVL': 'Lỗi hệ thống khi tạo NVL',
    'Lỗi khi bỏ qua tạm ứng': 'Lỗi khi bỏ qua tạm ứng',
    'Lỗi khi cấp phát vật tư': 'Lỗi khi cấp phát vật tư',
    'Lỗi khi cập nhật cửa hàng': 'Lỗi khi cập nhật cửa hàng',
    'Lỗi khi cập nhật người dùng': 'Lỗi khi cập nhật người dùng',
    'Lỗi khi cập nhật thông tin khách hàng': 'Lỗi khi cập nhật thông tin khách hàng',
    'Lỗi khi cập nhật trạng thái': 'Lỗi khi cập nhật trạng thái',
    'Lỗi khi lưu định mức': 'Lỗi khi lưu định mức',
    'Lỗi khi thêm vật tư': 'Lỗi khi thêm vật tư',
    'Lỗi khi tạo cửa hàng': 'Lỗi khi tạo cửa hàng',
    'Lỗi khi tạo người dùng': 'Lỗi khi tạo người dùng',
    'Lỗi khi tạo đơn mua.': 'Lỗi khi tạo đơn mua.',
    'Lỗi khi tạo đề nghị mua.': 'Lỗi khi tạo đề nghị mua.',
    'Lỗi khi vô hiệu hóa cửa hàng': 'Lỗi khi vô hiệu hóa cửa hàng',
    'Lỗi khi vô hiệu hóa tài khoản': 'Lỗi khi vô hiệu hóa tài khoản',
    'Mẫu "%(name)s" đã dùng để in %(count)d chứng từ nên không ': 'Mẫu "%(name)s" đã dùng để in %(count)d chứng từ nên không ',
    'Mẫu "%(name)s" đã xóa.': 'Mẫu "%(name)s" đã xóa.',
    'Người dùng không tìm thấy': 'Người dùng không tìm thấy',
    'Nhà cung cấp đã bị vô hiệu hóa': 'Nhà cung cấp đã bị vô hiệu hóa',
    'Nhà cung cấp đã được cập nhật': 'Nhà cung cấp đã được cập nhật',
    'Nhà cung cấp đã được tạo': 'Nhà cung cấp đã được tạo',
    'Order cannot be canceled': 'Không hủy được đơn hàng này',
    'Order confirmation issued under framework agreement %(n)s': 'Đã lập đơn đặt hàng theo hợp đồng nguyên tắc %(n)s',
    'Order created successfully': 'Đã tạo đơn hàng',
    'Order has been canceled successfully': 'Đã hủy đơn hàng',
    'Order not found': 'Không tìm thấy đơn hàng',
    'Order not found or access denied': 'Không tìm thấy đơn hàng hoặc không có quyền truy cập',
    'Order updated': 'Đã cập nhật đơn hàng',
    'PR đã gửi/duyệt/hủy — không sửa được.': 'PR đã gửi/duyệt/hủy — không sửa được.',
    'Payment cannot be edited (already confirmed or canceled)': 'Không sửa được phiếu thanh toán (đã xác nhận hoặc đã hủy)',
    'Payment marked as confirmed': 'Đã xác nhận thanh toán',
    'Payment recorded': 'Đã ghi nhận thanh toán',
    'Payment recorded in CASH — check input-VAT deductibility with your accountant': 'Thanh toán bằng TIỀN MẶT — hãy hỏi kế toán về điều kiện khấu trừ thuế GTGT đầu vào',
    'Payment report canceled successfully': 'Đã hủy phiếu thanh toán',
    'Payment report created successfully': 'Đã tạo phiếu thanh toán',
    'Payment report not found': 'Không tìm thấy phiếu thanh toán',
    'Payment report not found or access denied': 'Không tìm thấy phiếu thanh toán hoặc không có quyền truy cập',
    'Payment report updated successfully': 'Đã cập nhật phiếu thanh toán',
    'Penalty cannot exceed 8% (Điều 301 Luật Thương mại 2005)': 'Mức phạt không được vượt quá 8% (Điều 301 Luật Thương mại 2005)',
    'Please enter your email and password': 'Vui lòng nhập email và mật khẩu',
    'Price line added': 'Đã thêm dòng giá',
    'Product name is required': 'Vui lòng nhập tên sản phẩm',
    'Purchase order not found or access denied': 'Không tìm thấy đơn mua hoặc không có quyền truy cập',
    'Quantity and unit price cannot be negative': 'Số lượng và đơn giá không được âm',
    'Quotation approved successfully': 'Đã duyệt báo giá',
    'Quotation canceled successfully': 'Đã hủy báo giá',
    'Quotation cannot be edited after approval': 'Không sửa được báo giá sau khi đã duyệt',
    'Quotation created successfully': 'Đã tạo báo giá',
    'Quotation not found': 'Không tìm thấy báo giá',
    'Quotation not found or access denied': 'Không tìm thấy báo giá hoặc không có quyền truy cập',
    'Quotation updated successfully': 'Đã cập nhật báo giá',
    'Registration failed. Please try again.': 'Đăng ký không thành công. Vui lòng thử lại.',
    'Standardization rules reset to the defaults': 'Đã đặt lại quy tắc chuẩn hóa về mặc định',
    'Standardization rules saved': 'Đã lưu quy tắc chuẩn hóa',
    'Store selection is required': 'Vui lòng chọn cửa hàng',
    'Supplier invoice confirmed': 'Đã xác nhận hóa đơn nhà cung cấp',
    'Supplier invoice not found or access denied': 'Không tìm thấy hóa đơn nhà cung cấp hoặc không có quyền truy cập',
    'Supplier invoice recorded': 'Đã ghi nhận hóa đơn nhà cung cấp',
    'Theo quy tắc chuẩn hóa, "%(original)s" nên viết là ': 'Theo quy tắc chuẩn hóa, "%(original)s" nên viết là ',
    'This agreement can no longer be edited': 'Hợp đồng nguyên tắc này không còn sửa được',
    'This customer has no active framework agreement — create a contract instead': 'Khách hàng này chưa có hợp đồng nguyên tắc còn hiệu lực — hãy lập hợp đồng thường',
    'Title is required': 'Vui lòng nhập tên công việc',
    'Tên đăng nhập hoặc mật khẩu không đúng.': 'Tên đăng nhập hoặc mật khẩu không đúng.',
    'Tạo cửa hàng thành công': 'Tạo cửa hàng thành công',
    'Tạo người dùng thành công': 'Tạo người dùng thành công',
    'Unknown action': 'Thao tác không hợp lệ',
    'Unknown document type': 'Loại tài liệu không hợp lệ',
    'Vui lòng chọn tệp mẫu (.docx).': 'Vui lòng chọn tệp mẫu (.docx).',
    'Vui lòng điền đầy đủ các trường bắt buộc.': 'Vui lòng điền đầy đủ các trường bắt buộc.',
    'Vui lòng điền đầy đủ các trường.': 'Vui lòng điền đầy đủ các trường.',
    'Vui lòng điền đầy đủ tên và loại tài liệu.': 'Vui lòng điền đầy đủ tên và loại tài liệu.',
    'Workflow rules reset to the standard process': 'Đã đặt lại quy trình về quy trình chuẩn',
    'Workflow rules saved': 'Đã lưu quy tắc quy trình',
    'You have been logged out': 'Bạn đã đăng xuất',
    'Đã bỏ qua bước tạm ứng. Bạn có thể tạo chứng từ bàn giao ngay bây giờ.': 'Đã bỏ qua bước tạm ứng. Bạn có thể tạo chứng từ bàn giao ngay bây giờ.',
    'Đã cấp phát và trừ kho vật tư thành công.': 'Đã cấp phát và trừ kho vật tư thành công.',
    'Đã cập nhật nguyên vật liệu': 'Đã cập nhật nguyên vật liệu',
    'Đã cập nhật thông tin công ty.': 'Đã cập nhật thông tin công ty.',
    'Đã cập nhật trạng thái kế hoạch sản xuất': 'Đã cập nhật trạng thái kế hoạch sản xuất',
    'Đã cập nhật trạng thái đơn mua.': 'Đã cập nhật trạng thái đơn mua.',
    'Đã cập nhật trạng thái đề nghị mua.': 'Đã cập nhật trạng thái đề nghị mua.',
    'Đã cập nhật tình trạng tiến độ': 'Đã cập nhật tình trạng tiến độ',
    'Đã cập nhật đơn mua.': 'Đã cập nhật đơn mua.',
    'Đã cập nhật đề nghị mua.': 'Đã cập nhật đề nghị mua.',
    'Đã lưu cài đặt, nhưng KHÔNG đọc được danh sách tài ': 'Đã lưu cài đặt, nhưng KHÔNG đọc được danh sách tài ',
    'Đã lưu cấu hình trường mở rộng': 'Đã lưu cấu hình trường mở rộng',
    'Đã lưu định mức để tái sử dụng': 'Đã lưu định mức để tái sử dụng',
    'Đã nhập kho %(gr)s — tồn kho đã tăng.': 'Đã nhập kho %(gr)s — tồn kho đã tăng.',
    'Đã thêm vật tư vào kế hoạch': 'Đã thêm vật tư vào kế hoạch',
    'Đã tạo %(n)s đơn mua từ đề nghị.': 'Đã tạo %(n)s đơn mua từ đề nghị.',
    'Đã tạo %(n)s đơn mua từ đề xuất.': 'Đã tạo %(n)s đơn mua từ đề xuất.',
    'Đã tạo tài liệu (%(fmt)s) thành công.': 'Đã tạo tài liệu (%(fmt)s) thành công.',
    'Đã tạo tài liệu nhưng không chuyển được sang PDF — đã lưu dạng DOCX.': 'Đã tạo tài liệu nhưng không chuyển được sang PDF — đã lưu dạng DOCX.',
    'Đã tạo đơn mua %(po)s.': 'Đã tạo đơn mua %(po)s.',
    'Đã tạo đề nghị mua %(pr)s.': 'Đã tạo đề nghị mua %(pr)s.',
    'Đã xóa vật tư': 'Đã xóa vật tư',
    'Đã đăng xuất.': 'Đã đăng xuất.',
    'Đơn mua đã gửi/hủy — không sửa được.': 'Đơn mua đã gửi/hủy — không sửa được.',
    'Đơn vị đã bị vô hiệu hóa': 'Đơn vị đã bị vô hiệu hóa',
    'Đơn vị đã được cập nhật': 'Đơn vị đã được cập nhật',
    'Đơn vị đã được tạo': 'Đơn vị đã được tạo',
})


# --- Status labels. A column read half in Vietnamese and half in English is
# --- harder to scan than either language alone. ---
TRANSLATIONS['vi'].update({
    'Submitted': 'Đã gửi duyệt',
    'Converted': 'Đã chuyển đơn mua',
    'Partially Received': 'Nhận một phần',
    'In Production': 'Đang sản xuất',
    'Validating': 'Đang nghiệm thu',
    'Validated': 'Đã nghiệm thu',
    'Finished': 'Đã kết thúc',
    'Sent': 'Đã gửi',
    'Partially Paid': 'Thanh toán một phần',
    'Expired': 'Hết hiệu lực',
    'Đang hiệu lực': 'Đang hiệu lực',
    'Tạm ngưng': 'Tạm ngưng',
    'Đã chấm dứt': 'Đã chấm dứt',
    'Hết hiệu lực': 'Hết hiệu lực',
})

TRANSLATIONS['vi'].update({
    'Lưu ý': 'Lưu ý',
    'Hành động này không thể hoàn tác. Đơn hàng sẽ được đánh dấu là đã hủy.':
        'Hành động này không thể hoàn tác. Đơn hàng sẽ được đánh dấu là đã hủy.',
    'Vui lòng nhập lý do hủy đơn hàng...': 'Vui lòng nhập lý do hủy đơn hàng...',
    'Bảo lưu mọi quyền.': 'Bảo lưu mọi quyền.',
    'Order Code': 'Mã đơn hàng',
    'Value': 'Giá trị',
})

TRANSLATIONS['vi'].update({
    'Kế hoạch đang chờ nghiệm thu nên danh mục vật tư đã khóa. Dùng “Từ chối (làm lại)” để mở lại cho chỉnh sửa.':
        'Kế hoạch đang chờ nghiệm thu nên danh mục vật tư đã khóa. Dùng “Từ chối (làm lại)” để mở lại cho chỉnh sửa.',
    'Kế hoạch đã chốt và đang sản xuất nên danh mục vật tư đã khóa — để số liệu cấp phát và giá vốn khớp với lệnh đã chốt. Từ trạng thái này chỉ có thể “Hoàn thành” hoặc “Hủy”.':
        'Kế hoạch đã chốt và đang sản xuất nên danh mục vật tư đã khóa — để số liệu cấp phát và giá vốn khớp với lệnh đã chốt. Từ trạng thái này chỉ có thể “Hoàn thành” hoặc “Hủy”.',
    'Kế hoạch đã qua giai đoạn sản xuất nên danh mục vật tư đã khóa.':
        'Kế hoạch đã qua giai đoạn sản xuất nên danh mục vật tư đã khóa.',
})

TRANSLATIONS['vi'].update({
    'Bước nào cần điều kiện gì': 'Bước nào cần điều kiện gì',
    'Mỗi ô là một cặp (bước, điều kiện). Chọn mức ràng buộc, để trống nghĩa là bước đó không phụ thuộc điều kiện này.':
        'Mỗi ô là một cặp (bước, điều kiện). Chọn mức ràng buộc, để trống nghĩa là bước đó không phụ thuộc điều kiện này.',
    'Bật/tắt và lời nhắc khi bị chặn': 'Bật/tắt và lời nhắc khi bị chặn',
    'Các quy tắc đang có ở trên, liệt kê từng dòng. Tại đây bạn tạm tắt một quy tắc mà không xóa nó, và sửa câu thông báo người dùng nhìn thấy khi bị chặn. Mức ràng buộc thì sửa ở bảng trên.':
        'Các quy tắc đang có ở trên, liệt kê từng dòng. Tại đây bạn tạm tắt một quy tắc mà không xóa nó, và sửa câu thông báo người dùng nhìn thấy khi bị chặn. Mức ràng buộc thì sửa ở bảng trên.',
})

TRANSLATIONS['vi'].update({
    'Trường nào được chuẩn hóa thế nào': 'Trường nào được chuẩn hóa thế nào',
    'Mỗi trường văn bản đã là một dòng sẵn ở đây, nên không có nút “Tạo mới”: tick vào ô là áp dụng, bỏ tick hết cả dòng là thôi không chuẩn hóa trường đó nữa.':
        'Mỗi trường văn bản đã là một dòng sẵn ở đây, nên không có nút “Tạo mới”: tick vào ô là áp dụng, bỏ tick hết cả dòng là thôi không chuẩn hóa trường đó nữa.',
})

TRANSLATIONS['vi'].update({'Tổng quan': 'Tổng quan'})

TRANSLATIONS['vi'].update({
    'Các báo cáo': 'Các báo cáo',
    'Ai đang nợ, nợ bao nhiêu, và khoản nào đang chờ xác nhận.':
        'Ai đang nợ, nợ bao nhiêu, và khoản nào đang chờ xác nhận.',
})

TRANSLATIONS['vi'].update({
    'In hợp đồng nguyên tắc': 'In hợp đồng nguyên tắc',
    'In đơn đặt hàng': 'In đơn đặt hàng',
})

TRANSLATIONS['vi'].update({'Số này đã được dùng rồi.': 'Số này đã được dùng rồi.'})
