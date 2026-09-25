# Spatial Index Lab (SIL)

Dự án nghiên cứu, thực nghiệm và tái xây dựng các mô hình chỉ mục không gian `Spatial Index` cốt lõi. 

Mục tiêu của dự án là mô phỏng lại cơ chế hoạt động ngầm của các hệ quản trị cơ sở dữ liệu không gian (như GiST index trong PostGIS hay lõi thư viện GEOS) bằng Python. Các mô hình được benchmark trên tập dữ liệu không gian thực tế: **Thửa đất (Parcel)** và **Mạng lưới đường (Road)** tại khu vực Hiệp Bình Chánh (HBC), TP.HCM.