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
TRANSLATIONS['vi'].update({'(overall)': '(chung)', 'Account Holder': 'Chủ tài khoản', 'Account Number': 'Số tài khoản', 'Add Supplier': 'Thêm nhà cung cấp', 'Add material': 'Thêm vật tư', 'Additional Info': 'Thông tin bổ sung', 'Additional Information': 'Thông tin bổ sung', 'Address or location': 'Địa chỉ / nơi chốn', 'Alert when total stock falls below this level': 'Cảnh báo khi tổng tồn kho xuống dưới mức này', 'All materials are above their minimum stock level.': 'Tất cả vật tư đều trên mức tồn tối thiểu.', 'Amount in Words:': 'Số tiền bằng chữ:', 'Are you sure you want to delete': 'Bạn có chắc muốn xóa', 'Bank': 'Ngân hàng', 'Bank Account Info:': 'Thông tin tài khoản ngân hàng:', 'Business Registration No.': 'Số ĐKKD/GPKD', 'Cancellation Notice (days)': 'Số ngày báo trước khi hủy', 'Cancellation Notice:': 'Báo trước khi hủy:', 'Certifications': 'Chứng nhận', 'Composition': 'Thành phần', 'Composition & Appearance': 'Thành phần & Ngoại quan', 'Configure up to 10 custom fields per document type. Enabled fields appear on the create form.': 'Cấu hình tối đa 10 trường tùy chỉnh cho mỗi loại chứng từ. Trường được bật sẽ hiện trên biểu mẫu tạo.', 'Contact': 'Liên hệ', 'Contact Person': 'Người liên hệ', 'Contract Content': 'Nội dung hợp đồng', 'Contract Date': 'Ngày hợp đồng', 'Contract Start Date': 'Ngày bắt đầu hợp đồng', 'Contract Status': 'Trạng thái hợp đồng', 'Country of Origin': 'Xuất xứ', 'Data Type': 'Kiểu dữ liệu', 'Days to Complete': 'Số ngày hoàn thành', 'Days to Complete:': 'Số ngày hoàn thành:', 'Deactivate this supplier?': 'Ngừng hoạt động nhà cung cấp này?', 'Delete Document': 'Xóa tài liệu', 'Delete this material line?': 'Xóa dòng vật tư này?', 'Dimensions & Weight': 'Kích thước & Trọng lượng', 'Document Type': 'Loại tài liệu', 'Durability': 'Độ bền', 'Durability (Martindale)': 'Độ bền (Martindale)', 'Edit Supplier': 'Sửa nhà cung cấp', 'Extension Fields': 'Trường mở rộng', 'Field': 'Trường', 'Filename': 'Tên tệp', 'Finish': 'Hoàn thiện bề mặt', 'Fire Resistance': 'Chống cháy', 'Foam Density': 'Mật độ mút', 'Foam Density (kg/m³)': 'Mật độ mút (kg/m³)', 'For item': 'Cho hạng mục', 'Handover Date *': 'Ngày bàn giao *', 'Handover Time': 'Thời gian bàn giao', 'Hardness': 'Độ cứng', 'Hardness / Grade': 'Độ cứng / Cấp', 'Image': 'Hình ảnh', 'In stock': 'Tồn kho', 'Issued': 'Đã cấp', 'Items to produce': 'Hạng mục cần sản xuất', 'Label': 'Nhãn', 'Lead Time': 'Thời gian giao hàng', 'Lead Time (days)': 'Thời gian giao (ngày)', 'Low Stock Materials': 'Vật tư tồn thấp', 'Manage supplier records. Assign suppliers when creating materials.': 'Quản lý nhà cung cấp. Gán nhà cung cấp khi tạo vật tư.', 'Manage suppliers': 'Quản lý nhà cung cấp', 'Materials needed': 'Vật tư cần dùng', 'Min level': 'Mức tối thiểu', 'Name of contact': 'Tên người liên hệ', 'No items recorded.': 'Chưa có hạng mục nào.', 'No materials yet. Add materials below or save/apply a norm.': 'Chưa có vật tư. Thêm bên dưới hoặc lưu/áp dụng định mức.', 'No supplier': 'Không có nhà cung cấp', 'No supplier assigned.': 'Chưa gán nhà cung cấp.', 'No suppliers yet. Add one to get started.': 'Chưa có nhà cung cấp. Thêm mới để bắt đầu.', 'None': 'Không có', 'On': 'Bật', 'Order': 'Đơn hàng', 'Origin & Compliance': 'Xuất xứ & Tuân thủ', 'Pattern': 'Họa tiết', 'Payment Bank Account': 'Tài khoản ngân hàng nhận thanh toán', 'Payment Bank:': 'Ngân hàng thanh toán:', 'Payment Type': 'Loại thanh toán', 'Product / Work': 'Sản phẩm / Công việc', 'Production Plan': 'Kế hoạch sản xuất', 'Quality & Performance': 'Chất lượng & Hiệu năng', 'Quotation Ref. Date:': 'Ngày báo giá tham chiếu:', 'Rating': 'Đánh giá', 'Reason': 'Lý do', 'Reference Contract:': 'Hợp đồng tham chiếu:', 'Referenced Contract': 'Hợp đồng tham chiếu', 'Remaining Balance:': 'Còn lại phải trả:', 'Required': 'Bắt buộc', 'Roll Length': 'Chiều dài cuộn', 'Roll Length (m)': 'Chiều dài cuộn (m)', 'Save as norm': 'Lưu định mức', 'Save material list of this item as a reusable norm?': 'Lưu danh sách vật tư của hạng mục này thành định mức để dùng lại?', 'Save norm': 'Lưu định mức', 'Select a material': 'Chọn vật tư', 'Settings': 'Cài đặt', 'Signing Date *': 'Ngày ký *', 'Signing Date:': 'Ngày ký:', 'Start Date:': 'Ngày bắt đầu:', 'Subtotal': 'Cộng tiền hàng', 'Supplier': 'Nhà cung cấp', 'Supplier product code': 'Mã sản phẩm bên NCC', "Supplier's SKU": 'Mã SKU của NCC', 'Suppliers': 'Nhà cung cấp', 'The production plan is created automatically once the contract is signed.': 'Kế hoạch sản xuất được tạo tự động sau khi hợp đồng được ký.', 'Thickness': 'Độ dày', 'Thickness (mm)': 'Độ dày (mm)', 'This action cannot be undone. The file will be permanently removed.': 'Hành động này không thể hoàn tác. Tệp sẽ bị xóa vĩnh viễn.', 'UV Resistance': 'Kháng tia UV', 'Update': 'Cập nhật', 'Water Resistance': 'Kháng nước', 'Website': 'Website', 'Weight / Unit': 'Trọng lượng / Đơn vị', 'Weight/Unit': 'Trọng lượng/Đơn vị', 'Width': 'Khổ rộng', 'Width (cm)': 'Khổ rộng (cm)', 'Work Completion Summary:': 'Tóm tắt công việc hoàn thành:', 'days': 'ngày', 'e.g. 100% Polyester, Da bò thật Grade A': 'vd: 100% Polyester, Da bò thật Grade A', 'e.g. Công ty TNHH Vải Thiên Hà': 'vd: Công ty TNHH Vải Thiên Hà', 'e.g. Mét vuông - dùng cho vải và da': 'vd: Mét vuông - dùng cho vải và da', 'e.g. PO Number': 'vd: Số PO', 'e.g. Vải bọc': 'vd: Vải bọc', 'from contract — read-only': 'lấy từ hợp đồng — chỉ đọc', 'Purchase Suggestions': 'Đề xuất mua hàng', 'Low Stock': 'Tồn kho thấp', 'Code': 'Mã', 'Name': 'Tên', 'items': 'sản phẩm', 'Deactivate this user?': 'Vô hiệu hóa người dùng này?', 'Deactivate this store?': 'Vô hiệu hóa cửa hàng này?', 'Purchase Orders': 'Đơn mua hàng', 'Notes': 'Ghi chú', 'Quotation': 'Báo giá', 'Contract': 'Hợp đồng', 'Handover': 'Bàn giao', 'Payment': 'Thanh toán', 'Purchase_order': 'Đơn mua hàng', 'Goods_receipt': 'Phiếu nhập kho', 'Purchase Requisitions': 'Đề nghị mua hàng', 'Goods Receipts': 'Phiếu nhập kho', 'Purchase_requisition': 'Đề nghị mua hàng'})
