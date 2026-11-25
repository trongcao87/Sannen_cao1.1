// sannen.dcl - cac hop thoai cua menu SAN NEN (AutoCAD 2022).
//
// QUY UOC (quan trong):
//  * File nay CHI GOM ASCII. DCL doc theo bang ma he thong (ANSI), khong chac hieu UTF-8 - khong the kiem
//    chung duoc tren may khong co giao dien. Vi vay MOI CHU HIEN THI CO DAU deu do sannen.lsp dat bang set_tile
//    ngay sau new_dialog (ham sn:vn / sn:vn-ds), nhu chuoi "tong dien tich o" da hien dung dau.
//  * set_tile chi doi duoc chu cua tile `text` (va nhan nut `button`). Toggle / edit_box / popup_list / boxed_*
//    KHONG doi duoc nhan => o day de `label = ""` va dat mot tile `text` (khoa n_...) ben canh de LISP viet chu co dau.
//    Nhom lua chon (truoc la radio) doi thanh popup_list - noi dung danh sach do LISP nap (add_list) nen co dau.
//  * Thanh tieu de hop thoai (label cua dialog) khong doi duoc => de ASCII ngan; tieu de day du nam o tile t_ten.
//  * Nhan nut ASCII la du phong neu set_tile khong doi duoc label cua nut.
//  * Dong ghi chu dai dung 2-3 tile text xep doc (t_tt, t_tt2, t_tt3) - LISP tu ngat dong (sn:tt) de khong bi cat.
//  * Key co tien to: e_ o nhap - t_ chu/toggle - n_ chu nhan canh o - b_ nut - p_ popup - l_ danh sach.
//    Moi key la duy nhat TRONG tung hop thoai (test_gd12_lisp.py kiem tra).

// ---- Bang dieu khien trung tam (SN_QL) -----------------------------------------------------------------
// Gom: thong tin lo + 3 cong + canh bao ket qua cu; danh sach NHOM doi tuong (so doi tuong, Hien/An);
// khung so lieu chi tiet theo nhom; cac nut dieu phoi. list_box dung `fixed_width_font` + `tabs` de thang cot.
// Cao khoang 28 dong luoi, rong khoang 126 ky tu (vua man hinh 1366).
sn_ql : dialog {
  label = "SAN NEN - Bang dieu khien";
  : text { key = "t_ten"; value = ""; width = 124; }
  : text { key = "t_lo"; value = ""; width = 124; }
  : text { key = "t_buoc"; value = ""; width = 124; }
  : text { key = "t_cong"; value = ""; width = 124; }
  : text { key = "t_cu"; value = ""; width = 124; }
  : text { key = "t_cu2"; value = ""; width = 124; }
  : row {
    : column {
      : text { key = "t_cot"; value = ""; width = 60; }
      : list_box { key = "l_nhom"; width = 60; height = 11; multiple_select = true; fixed_width_font = true; tabs = "28 46"; tab_truncate = true; }
      : row {
        : button { key = "b_hien"; label = "Hien"; width = 10; }
        : button { key = "b_an"; label = "An"; width = 10; }
        : button { key = "b_chi"; label = "Chi hien nhom nay"; width = 26; }
      }
      : row {
        : button { key = "b_hien_het"; label = "Hien tat ca SAN NEN"; width = 22; }
        : button { key = "b_an_het"; label = "An tat ca SAN NEN"; width = 20; }
        : button { key = "b_zoom"; label = "Zoom toi nhom"; width = 16; }
      }
    }
    : column {
      : text { key = "t_cttieu"; value = ""; width = 62; }
      : list_box { key = "l_ct"; width = 62; height = 14; fixed_width_font = true; tabs = "40"; tab_truncate = true; }
    }
  }
  : row {
    : button { key = "b_tin3d"; label = "Xem 3D..."; width = 22; }
    : button { key = "b_xem3d"; label = "Trinh xem HTML"; width = 22; }
    : button { key = "b_luoi"; label = "Hieu chinh luoi..."; width = 22; }
    : button { key = "b_matcat"; label = "Mat cat..."; width = 22; }
    : button { key = "b_capdo"; label = "Cao do dinh..."; width = 22; }
  }
  : row {
    : button { key = "b_canhbao"; label = "Canh bao QC..."; width = 20; }
    : button { key = "b_bang"; label = "Bang bieu..."; width = 18; }
    : button { key = "b_tinh"; label = "Tinh lai"; width = 16; }
    : button { key = "b_ve"; label = "Ve lai nhom dang chon"; width = 26; }
    : button { key = "b_duyet"; label = "Duyet cong..."; width = 18; }
    : button { key = "b_lammoi"; label = "Lam moi"; width = 14; }
    : button { key = "b_dong"; label = "Dong"; is_cancel = true; width = 12; }
  }
  : text { key = "t_tt"; value = ""; width = 124; }
  : text { key = "t_tt2"; value = ""; width = 124; }
  : text { key = "t_tt3"; value = ""; width = 124; }
}

// ---- Xem 3D cua TIN ------------------------------------------------------------------------------------
sn_tin3d : dialog {
  label = "SAN NEN - Xem 3D";
  : text { key = "t_ten"; value = ""; width = 68; }
  : text { key = "t_tieu"; value = ""; width = 68; }
  : row {
    : text { key = "n_bm"; value = ""; width = 14; }
    : popup_list { key = "p_bemat"; label = ""; edit_width = 50; }
  }
  : row { : toggle { key = "t_iso"; label = ""; value = "1"; } : text { key = "n_iso"; value = ""; width = 60; } }
  : row { : toggle { key = "t_bong"; label = ""; value = "1"; } : text { key = "n_bong"; value = ""; width = 60; } }
  : row { : toggle { key = "t_chi3d"; label = ""; value = "0"; } : text { key = "n_chi3d"; value = ""; width = 60; } }
  : text { key = "t_tt"; value = ""; width = 68; }
  : text { key = "t_tt2"; value = ""; width = 68; }
  : text { key = "t_tt3"; value = ""; width = 68; }
  : row {
    : button { key = "b_hien"; label = "Hien thi"; is_default = true; width = 18; }
    : button { key = "b_tat"; label = "Tat 3D"; width = 18; }
    : button { key = "b_khoiphuc"; label = "Khoi phuc lop"; width = 18; }
  }
  : row {
    : button { key = "b_xem"; label = "Mo trinh xem 3D (HTML)"; width = 30; }
    : button { key = "b_dong"; label = "Dong"; is_cancel = true; width = 18; }
  }
}

// ---- Hieu chinh luoi (tuong duong DD_TAOLUOI + menu Ctrl + chuot phai cua SNVN) ----------------------
sn_luoi : dialog {
  label = "SAN NEN - Tao va hieu chinh luoi";
  : text { key = "t_ten"; value = ""; width = 74; }
  : text { key = "t_tieu"; value = ""; width = 74; }
  : text { key = "t_tieu2"; value = ""; width = 74; }
  : boxed_column {
    label = "";
    : text { key = "t_nhom1"; value = ""; width = 70; }
    : row {
      : text { key = "n_kt_mau"; value = ""; width = 20; }
      : popup_list { key = "p_kt_mau"; label = ""; edit_width = 16; }
      : text { key = "n_kt"; value = ""; width = 12; }
      : edit_box { key = "e_kt"; label = ""; edit_width = 6; }
      : text { key = "n_goc"; value = ""; width = 10; }
      : edit_box { key = "e_goc"; label = ""; edit_width = 6; }
    }
    : row {
      : button { key = "b_vung"; label = "Quet / Chon lo tren CAD..."; width = 36; }
      : button { key = "b_diem_dat"; label = "Chon diem dat luoi..."; width = 34; }
    }
    : row {
      : text { key = "n_ktvung"; value = ""; width = 28; }
      : text { key = "t_ktvung"; value = ""; width = 42; }
    }
    : text { key = "t_gocluoi"; value = ""; width = 70; }
    : row {
      : text { key = "n_cot"; value = ""; width = 22; }
      : edit_box { key = "e_cot"; label = ""; edit_width = 44; }
    }
    : row {
      : text { key = "n_hang"; value = ""; width = 22; }
      : edit_box { key = "e_hang"; label = ""; edit_width = 44; }
    }
    : row {
      : text { key = "n_ns"; value = ""; width = 28; }
      : edit_box { key = "e_ns"; label = ""; edit_width = 8; }
      : text { key = "n_kieu"; value = ""; width = 6; }
      : popup_list { key = "p_kieu"; label = ""; edit_width = 18; }
    }
  }
  : text { key = "t_tt"; value = ""; width = 74; }
  : text { key = "t_tt2"; value = ""; width = 74; }
  : text { key = "t_tt3"; value = ""; width = 74; }
  : boxed_column {
    label = "";
    : text { key = "t_nhom2"; value = ""; width = 60; }
    : row {
      : text { key = "n_chiso"; value = ""; width = 8; }
      : edit_box { key = "e_chiso"; label = ""; edit_width = 6; }
      : text { key = "n_ktdoi"; value = ""; width = 16; }
      : edit_box { key = "e_ktdoi"; label = ""; edit_width = 8; }
    }
    : row {
      : button { key = "b_doi_cot"; label = "Doi KT cot"; width = 17; }
      : button { key = "b_doi_hang"; label = "Doi KT hang"; width = 17; }
      : button { key = "b_chen_cot"; label = "Chen sau cot"; width = 17; }
      : button { key = "b_chen_hang"; label = "Chen sau hang"; width = 17; }
    }
    : row {
      : button { key = "b_xoa_cot"; label = "Xoa cot"; width = 17; }
      : button { key = "b_xoa_hang"; label = "Xoa hang"; width = 17; }
    }
  }
  : row {
    : button { key = "b_di_chuyen"; label = "Di chuyen luoi..."; width = 18; }
    : button { key = "b_xoay"; label = "Xoay luoi..."; width = 18; }
    : button { key = "b_gan_cd"; label = "Gan cao do nut"; width = 18; }
    : button { key = "b_ve_lot"; label = "Ve lot.yaml"; width = 18; }
  }
  : row {
    : button { key = "b_ap_dung"; label = "Tao luoi..."; is_default = true; width = 18; }
    : button { key = "b_xoa_luoi"; label = "Xoa luoi"; width = 18; }
    : button { key = "b_sua_cd"; label = "Sua cao do..."; width = 20; }
    : button { key = "b_dong"; label = "Dong"; is_cancel = true; width = 14; }
  }
}

// ---- Hieu chinh cao do dinh luoi (DD_NANGCDTK + sua tung nut cua SNVN) -------------------------------
sn_capdo : dialog {
  label = "SAN NEN - Cao do dinh";
  : text { key = "t_ten"; value = ""; width = 62; }
  : text { key = "t_tieu"; value = ""; width = 62; }
  : text { key = "t_chon"; value = ""; width = 62; }
  : button { key = "b_chon"; label = "Chon dinh tren ban ve..."; width = 34; }
  : row {
    : text { key = "n_che"; value = ""; width = 16; }
    : popup_list { key = "p_che"; label = ""; edit_width = 44; }
  }
  : row {
    : text { key = "n_gt"; value = ""; width = 16; }
    : edit_box { key = "e_gt"; label = ""; edit_width = 10; }
    : text { key = "n_bemat"; value = ""; width = 10; }
    : popup_list { key = "p_bemat"; label = ""; edit_width = 24; }
  }
  : row {
    : text { key = "n_lydo"; value = ""; width = 16; }
    : edit_box { key = "e_lydo"; label = ""; edit_width = 44; }
  }
  : text { key = "t_tt"; value = ""; width = 62; }
  : text { key = "t_tt2"; value = ""; width = 62; }
  : text { key = "t_tt3"; value = ""; width = 62; }
  : row {
    : button { key = "b_ap_dung"; label = "Ap dung"; is_default = true; width = 16; }
    : button { key = "b_dong"; label = "Dong"; is_cancel = true; width = 16; }
  }
}

// ---- Mat cat dia hinh --------------------------------------------------------------------------------
sn_matcat : dialog {
  label = "SAN NEN - Mat cat";
  : text { key = "t_ten"; value = ""; width = 66; }
  : text { key = "t_tieu"; value = ""; width = 66; }
  : text { key = "t_tieu2"; value = ""; width = 66; }
  : row {
    : text { key = "n_ten"; value = ""; width = 24; }
    : edit_box { key = "e_ten"; label = ""; edit_width = 14; }
  }
  : row {
    : text { key = "n_buoc"; value = ""; width = 24; }
    : edit_box { key = "e_buoc"; label = ""; edit_width = 8; }
  }
  : row {
    : text { key = "n_tl"; value = ""; width = 24; }
    : edit_box { key = "e_tl"; label = ""; edit_width = 8; }
  }
  : button { key = "b_tuyen"; label = "Chon tuyen cat A - B..."; width = 34; }
  : text { key = "t_ab"; value = ""; width = 66; }
  : text { key = "t_ab2"; value = ""; width = 66; }
  : button { key = "b_diem"; label = "Chon diem dat bieu do..."; width = 34; }
  : text { key = "t_dd"; value = ""; width = 66; }
  : text { key = "t_dd2"; value = ""; width = 66; }
  : text { key = "t_dd3"; value = ""; width = 66; }
  : row {
    : button { key = "b_tao"; label = "Tao mat cat"; is_default = true; width = 18; }
    : button { key = "b_dong"; label = "Dong"; is_cancel = true; width = 18; }
  }
}

// ---- Bang bieu -----------------------------------------------------------------------------------------
sn_bang : dialog {
  label = "SAN NEN - Bang bieu";
  : text { key = "t_ten"; value = ""; width = 62; }
  : text { key = "t_tieu"; value = ""; width = 62; }
  : row {
    : text { key = "n_loai"; value = ""; width = 12; }
    : popup_list { key = "p_loai"; label = ""; edit_width = 46; }
  }
  : text { key = "t_tt"; value = ""; width = 62; }
  : text { key = "t_tt2"; value = ""; width = 62; }
  : text { key = "t_tt3"; value = ""; width = 62; }
  : row {
    : button { key = "b_chen"; label = "Chen vao ban ve"; is_default = true; width = 20; }
    : button { key = "b_excel"; label = "Xuat Excel + ho so"; width = 22; }
  }
  : row {
    : button { key = "b_thumuc"; label = "Mo thu muc xuat"; width = 20; }
    : button { key = "b_dong"; label = "Dong"; is_cancel = true; width = 22; }
  }
}

// ---- Canh bao / QC -------------------------------------------------------------------------------------
sn_canhbao : dialog {
  label = "SAN NEN - Canh bao va QC";
  : text { key = "t_ten"; value = ""; width = 90; }
  : text { key = "t_tieu"; value = ""; width = 90; }
  : row { : toggle { key = "t_chi_chan"; label = ""; value = "0"; } : text { key = "n_chi_chan"; value = ""; width = 40; } }
  : list_box { key = "l_ds"; width = 90; height = 14; multiple_select = false; }
  : text { key = "t_tt"; value = ""; width = 90; }
  : text { key = "t_tt2"; value = ""; width = 90; }
  : text { key = "t_tt3"; value = ""; width = 90; }
  : row {
    : button { key = "b_zoom"; label = "Zoom toi"; is_default = true; width = 18; }
    : button { key = "b_lammoi"; label = "Lam moi"; width = 18; }
    : button { key = "b_dong"; label = "Dong"; is_cancel = true; width = 18; }
  }
}

// ---- Duyet cong (nguoi quyet, agent khong tu duyet) ----------------------------------------------------
sn_duyet : dialog {
  label = "SAN NEN - Duyet cong";
  : text { key = "t_ten"; value = ""; width = 66; }
  : text { key = "t_tieu"; value = ""; width = 66; }
  : text { key = "t_tieu2"; value = ""; width = 66; }
  : row {
    : text { key = "n_cong"; value = ""; width = 16; }
    : popup_list { key = "p_cong"; label = ""; edit_width = 46; }
  }
  : text { key = "t_c1"; value = ""; width = 66; }
  : text { key = "t_c2"; value = ""; width = 66; }
  : text { key = "t_c3"; value = ""; width = 66; }
  : row {
    : text { key = "n_nguoi"; value = ""; width = 24; }
    : edit_box { key = "e_nguoi"; label = ""; edit_width = 34; }
  }
  : row {
    : text { key = "n_bc"; value = ""; width = 24; }
    : edit_box { key = "e_bc"; label = ""; edit_width = 40; }
  }
  : text { key = "t_tt"; value = ""; width = 66; }
  : text { key = "t_tt2"; value = ""; width = 66; }
  : text { key = "t_tt3"; value = ""; width = 66; }
  : row {
    : button { key = "b_duyet"; label = "Duyet cong"; is_default = true; width = 18; }
    : button { key = "b_dong"; label = "Dong"; is_cancel = true; width = 18; }
  }
}

// ---- Khoi tao be mat thu cong (DD_DH cua SNVN: MHTN goc + MHTK tinh toan + Breakline + Bien lo) ------
sn_taomat : dialog {
  label = "SAN NEN - Quan ly mo hinh dia hinh";
  : text { key = "t_ten"; value = ""; width = 74; }
  : text { key = "t_tieu"; value = ""; width = 74; }
  : text { key = "t_tieu2"; value = ""; width = 74; }
  : boxed_column {
    label = "";
    : text { key = "t_nhom_bm"; value = ""; width = 68; }
    : row {
      : text { key = "n_loai_bm"; value = ""; width = 22; }
      : popup_list { key = "p_loai_bm"; label = ""; edit_width = 44; }
    }
    : row {
      : text { key = "n_loc"; value = ""; width = 68; }
    }
    : row {
      : toggle { key = "t_loc_diem"; label = ""; value = "1"; } : text { key = "n_loc_diem"; value = ""; width = 16; }
      : toggle { key = "t_loc_khoi"; label = ""; value = "1"; } : text { key = "n_loc_khoi"; value = ""; width = 16; }
      : toggle { key = "t_loc_chu"; label = ""; value = "1"; } : text { key = "n_loc_chu"; value = ""; width = 18; }
    }
    : row {
      : toggle { key = "t_loc_line"; label = ""; value = "1"; } : text { key = "n_loc_line"; value = ""; width = 16; }
      : toggle { key = "t_loc_pl3d"; label = ""; value = "1"; } : text { key = "n_loc_pl3d"; value = ""; width = 16; }
      : toggle { key = "t_loc_pl2d"; label = ""; value = "1"; } : text { key = "n_loc_pl2d"; value = ""; width = 18; }
    }
    : row {
      : button { key = "b_cad_moc"; label = "Chon MHTN tren CAD..."; width = 24; }
      : button { key = "b_xls_moc"; label = "Chon MHTN tu Excel..."; width = 24; }
    }
    : text { key = "t_tt_moc"; value = ""; width = 68; }
    : row {
      : button { key = "b_cad_do"; label = "Chon MHTK tren CAD..."; width = 24; }
      : button { key = "b_xls_do"; label = "Chon MHTK tu Excel..."; width = 24; }
    }
    : text { key = "t_tt_do"; value = ""; width = 68; }
  }
  : boxed_column {
    label = "";
    : text { key = "t_nhom_bl"; value = ""; width = 68; }
    : row {
      : button { key = "b_chon_dg"; label = "Chon duong Breakline..."; width = 24; }
      : button { key = "b_chon_bien"; label = "Chon bien lo (ranh)..."; width = 24; }
      : button { key = "b_chon_lt"; label = "Chon vung loai tru..."; width = 22; }
    }
    : text { key = "t_tt_dg"; value = ""; width = 68; }
    : text { key = "t_tt_bien"; value = ""; width = 68; }
  }
  : text { key = "t_tt"; value = ""; width = 74; }
  : text { key = "t_tt2"; value = ""; width = 74; }
  : text { key = "t_tt3"; value = ""; width = 74; }
  : row {
    : button { key = "b_tao_bm"; label = "Tao moi / Cap nhat MH"; is_default = true; width = 28; }
    : button { key = "b_dong"; label = "Thoat"; is_cancel = true; width = 18; }
  }
}
