;;; sannen.lsp — menu "SAN NỀN" cho AutoCAD 2022: kiểm tra, xem và xuất kết quả san nền ngay trong bản vẽ.
;;;
;;; PHÂN VAI: file này CHỈ lo giao diện (lệnh, hộp thoại, menu) và vẽ. Mọi phép tính nằm ở lõi Python
;;; (sannen-core) — LISP gọi cầu nối `python -m sannen_cad.cau_noi <lệnh>`, đọc kết quả dạng s-expression,
;;; và nạp file LISP vẽ (entmake) mà cầu nối sinh ra. Đối tượng kết quả mang XDATA "SANNEN":
;;;   (mã lô)(đợt)(hash)(loại)("k=v"...). Xem cad/README.md.
;;;
;;; NẠP:  APPLOAD → sannen.lsp  (hoặc (load "…/sannen.lsp")).  Cấu hình: %APPDATA%\SanNen\sannen.cfg
;;;       (tạo bằng cad/cai_dat_cad.ps1).  Gõ SN để mở menu dòng lệnh; menu thả xuống "SAN NỀN" tự được tạo.

(vl-load-com)
(regapp "SANNEN")

(setq *sn-phien-ban* "1.0.0")
(setq *sn-cfg* nil)        ; alist cấu hình (python, cad, lisp, lot)
(setq *sn-cho-lsp* nil)    ; file LISP vẽ đang chờ nạp sau khi đóng hộp thoại (lệnh `command` không chạy được trong hộp thoại)

;;; ===========================================================================================
;;; 1. TIỆN ÍCH CHUỖI / SỐ
;;; ===========================================================================================
(defun sn:thay (s tu den / p r k)                       ; thay mọi `tu` bằng `den`
  (setq r "" k 0)
  (while (setq p (vl-string-search tu s k))
    (setq r (strcat r (substr s (1+ k) (- p k)) den)
          k (+ p (strlen tu))))
  (strcat r (substr s (1+ k))))

(defun sn:cat (s) (vl-string-trim " \t\r\n" s))

(defun sn:chuoi-p (x) (eq (type x) 'STR))              ; AutoLISP KHÔNG có `stringp`

(defun sn:neu (a b) (if a a b))   ; "giá trị mặc định": `or` của AutoLISP trả T/nil, KHÔNG trả giá trị đầu tiên khác nil

(defun sn:chia (s tu / p k r)                           ; chia chuỗi theo `tu`
  (setq k 0)
  (while (setq p (vl-string-search tu s k))
    (setq r (cons (substr s (1+ k) (- p k)) r)
          k (+ p (strlen tu))))
  (reverse (cons (substr s (1+ k)) r)))

(defun sn:lap (ch n / r)                                ; lặp ký tự n lần
  (setq r "")
  (repeat n (setq r (strcat r ch)))
  r)

(defun sn:g (x / s)                                     ; số → chuỗi gọn (bỏ số 0 thừa)
  (setq s (rtos x 2 6))
  (if (vl-string-search "." s)
    (progn
      (while (= (substr s (strlen s)) "0") (setq s (substr s 1 (1- (strlen s)))))
      (if (= (substr s (strlen s)) ".") (setq s (substr s 1 (1- (strlen s)))))))
  s)

(defun sn:so (s) (if (and s (/= (sn:cat s) "")) (distof (sn:cat s) 2)))   ; chuỗi → số thực (nil nếu hỏng)

(defun sn:en (p) (strcat (rtos (car p) 2 4) "," (rtos (cadr p) 2 4)))      ; điểm → "E,N"

(defun sn:q (s)                                         ; bọc dấu nháy cho dòng lệnh cmd (bỏ nháy và `\` cuối)
  (setq s (sn:thay s "\"" "'"))
  (while (and (> (strlen s) 0) (= (substr s (strlen s)) "\\")) (setq s (substr s 1 (1- (strlen s)))))
  (strcat "\"" s "\""))

(defun sn:cat-dong (s)                                  ; bỏ xuống dòng để vừa một dòng
  (sn:thay (sn:thay (if s s "") "\n" " ") "\r" " "))

(defun sn:get (khoa lst) (cdr (assoc khoa lst)))

(defun sn:wrap (s w / ds r dong p)                       ; ngắt dòng theo từ, mỗi dòng ≤ w ký tự
  (setq ds (sn:chia (sn:cat-dong s) " ") dong "" r nil)
  (foreach p ds
    (cond ((= p "") nil)
          ((= dong "") (setq dong p))
          ((<= (+ (strlen dong) 1 (strlen p)) w) (setq dong (strcat dong " " p)))
          (T (setq r (cons dong r) dong p))))
  (if (/= dong "") (setq r (cons dong r)))
  (reverse r))

(defun sn:vs (x)                                        ; giá trị s-expression → chữ hiển thị
  (cond ((null x) "không")
        ((eq x T) "có")
        ((sn:chuoi-p x) x)
        ((eq (type x) 'INT) (itoa x))
        ((numberp x) (sn:g x))
        ((listp x) (apply 'strcat (mapcar '(lambda (i) (strcat (sn:vs i) " ")) x)))
        (T "?")))

(defun sn:in (x ind / it)                               ; in alist lồng nhau ra dòng lệnh
  (foreach it x
    (cond
      ((and (listp it) (sn:chuoi-p (car it)))
       (if (and (listp (cdr it)) (cdr it) (listp (cadr it)))
         (progn (prompt (strcat "\n" (sn:lap " " ind) (car it) ":")) (sn:in (cdr it) (+ ind 2)))
         (prompt (strcat "\n" (sn:lap " " ind) (car it) ": " (sn:vs (cdr it))))))
      (T (prompt (strcat "\n" (sn:lap " " ind) "- " (sn:vs it)))))))

(defun sn:thu (fn / r)                                  ; chạy fn, nuốt lỗi, trả kết quả hoặc nil
  (setq r (vl-catch-all-apply fn nil))
  (if (vl-catch-all-error-p r) nil r))

;;; ===========================================================================================
;;; 2. ĐỌC / GHI FILE UTF-8 (AutoCAD 2022 chưa có tham số mã hóa cho `open` → dùng ADODB.Stream)
;;; ===========================================================================================
(defun sn:doc-van-ban (f / st s)
  (if (and f (findfile f))
    (progn
      (setq st (vlax-create-object "ADODB.Stream"))
      (vlax-put-property st 'Type 2)
      (vlax-put-property st 'Charset "utf-8")
      (vlax-invoke st 'Open)
      (vlax-invoke st 'LoadFromFile (findfile f))
      (setq s (vlax-invoke st 'ReadText -1))
      (vlax-invoke st 'Close)
      (vlax-release-object st)
      s)))

(defun sn:ghi-van-ban (f txt / a b)                     ; ghi UTF-8 KHÔNG BOM (Python đọc trơn tru)
  (setq a (vlax-create-object "ADODB.Stream")
        b (vlax-create-object "ADODB.Stream"))
  (vlax-put-property a 'Type 2)
  (vlax-put-property a 'Charset "utf-8")
  (vlax-invoke a 'Open)
  (vlax-invoke a 'WriteText txt 0)
  (vlax-put-property a 'Position 0)
  (vlax-put-property a 'Type 1)
  (vlax-put-property a 'Position 3)                     ; bỏ 3 byte BOM
  (vlax-put-property b 'Type 1)
  (vlax-invoke b 'Open)
  (vlax-invoke a 'CopyTo b)
  (vlax-invoke b 'SaveToFile f 2)
  (vlax-invoke a 'Close)
  (vlax-invoke b 'Close)
  (vlax-release-object a)
  (vlax-release-object b)
  T)

(defun sn:dong-van-ban (f / s)                          ; danh sách các dòng của file UTF-8
  (if (setq s (sn:doc-van-ban f))
    (mapcar 'sn:cat (sn:chia (sn:thay s "\r" "") "\n"))))

;;; ===========================================================================================
;;; 3. CẤU HÌNH  (%APPDATA%\SanNen\sannen.cfg — hoặc biến môi trường SANNEN_CFG)
;;; ===========================================================================================
(defun sn:cfg-file ()
  (sn:neu (getenv "SANNEN_CFG") (strcat (getenv "APPDATA") "\\SanNen\\sannen.cfg")))

(defun sn:doc-cfg ( / r p)
  (setq r nil)
  (foreach d (sn:dong-van-ban (sn:cfg-file))
    (if (and (> (strlen d) 0) (/= (substr d 1 1) "#") (setq p (vl-string-search "=" d)))
      (setq r (cons (cons (strcase (sn:cat (substr d 1 p)) T) (sn:cat (substr d (+ p 2)))) r))))
  (setq *sn-cfg* (reverse r)))

(defun sn:cfg (khoa)
  (if (null *sn-cfg*) (sn:doc-cfg))
  (cdr (assoc khoa *sn-cfg*)))

(defun sn:ghi-cfg (khoa gia-tri / ds f dir txt)         ; cập nhật một khoá rồi ghi lại cả file
  (sn:doc-cfg)
  (if (assoc khoa *sn-cfg*)
    (setq ds (subst (cons khoa gia-tri) (assoc khoa *sn-cfg*) *sn-cfg*))
    (setq ds (append *sn-cfg* (list (cons khoa gia-tri)))))
  (setq f (sn:cfg-file) dir (vl-filename-directory f))
  (if (not (vl-file-directory-p dir)) (vl-mkdir dir))
  (setq txt "")
  (foreach i ds (setq txt (strcat txt (car i) "=" (cdr i) "\n")))
  (sn:ghi-van-ban f txt)
  (setq *sn-cfg* ds)
  gia-tri)

(defun sn:yaml-khoa (file khoa / r p v)                 ; đọc giá trị đơn giản `khoa: giá trị` trong lot.yaml
  (foreach d (sn:dong-van-ban file)
    (if (and (null r) (= (strlen d) (strlen (vl-string-left-trim " " d)))
             (wcmatch d (strcat khoa ":*")))
      (progn
        (setq v (sn:cat (substr d (+ (strlen khoa) 2))))
        (if (setq p (vl-string-search " #" v)) (setq v (sn:cat (substr v 1 p))))
        (setq r (vl-string-trim "\"'" v)))))
  r)

(defun sn:ma-lo ( / lot) (if (setq lot (sn:cfg "lot")) (sn:yaml-khoa (strcat lot "\\lot.yaml") "ma_lo")))
(defun sn:dot ( / lot v)
  (if (setq lot (sn:cfg "lot"))
    (if (setq v (sn:yaml-khoa (strcat lot "\\lot.yaml") "dot")) (atoi v) 1)
    1))

(defun sn:bao (msg) (prompt (strcat "\n" msg)) (princ))

(defun sn:can-lot ()                                     ; có lô hiện tại chưa? nếu chưa thì báo
  (cond ((and (sn:cfg "lot") (findfile (strcat (sn:cfg "lot") "\\lot.yaml"))) (sn:cfg "lot"))
        (T (sn:bao "Chưa chọn lô. Gõ SN_LOT để chọn thư mục lô (có lot.yaml).") nil)))

;;; ===========================================================================================
;;; 4. CẦU NỐI PYTHON  (sn:chay)
;;; ===========================================================================================
(defun sn:tmp () (sn:neu (getenv "SANNEN_TMP") (sn:neu (getenv "TEMP") "C:\\Temp")))

(defun sn:loi (msg) (list (cons "ok" nil) (cons "thong_bao" msg)))

(defun sn:doc-sx (f / s r)                               ; đọc file s-expression UTF-8 do cầu nối ghi
  (if (setq s (sn:doc-van-ban f))
    (progn
      (setq s (sn:thay (sn:thay s "\r" " ") "\n" " "))
      (setq r (vl-catch-all-apply 'read (list s)))
      (if (vl-catch-all-error-p r) nil r))))

(defun sn:chay (lenh args lsp? / py cad lot tmp ra lsp log cmd sh kq)
  ;; Chạy `python -m sannen_cad.cau_noi <lenh> --lot … <args> --ra …` và CHỜ xong. Trả alist
  ;; (("ok" . T/nil) ("thong_bao" . …) ("du_lieu" . …) ["_lsp" . đường dẫn]). lsp? = T: bảo cầu nối sinh file vẽ.
  (setq py (sn:cfg "python") cad (sn:cfg "cad") lot (sn:cfg "lot")
        tmp (sn:tmp)
        ra  (strcat tmp "\\sn_ra.txt")
        lsp (strcat tmp "\\sn_ve.lsp")
        log (strcat tmp "\\sn_log.txt"))
  (cond
    ((not (and py cad lot))
     (sn:loi "Chưa cấu hình: chạy cad\\cai_dat_cad.ps1 (python=, cad=) và SN_LOT (lot=)."))
    (T
     (vl-file-delete ra) (vl-file-delete lsp) (vl-file-delete log)
     (setq cmd (strcat "cmd /s /c \"set PYTHONIOENCODING=utf-8&& set PYTHONPATH=" cad ";%PYTHONPATH%&& "
                       "\"" py "\" -X utf8 -m sannen_cad.cau_noi " lenh
                       " --lot \"" lot "\" " args
                       " --ra \"" ra "\""
                       (if lsp? (strcat " --lsp \"" lsp "\"") "")
                       " > \"" log "\" 2>&1\""))
     (setq sh (vlax-create-object "WScript.Shell"))
     (vl-catch-all-apply 'vlax-invoke (list sh 'Run cmd 0 :vlax-true))     ; 0 = ẩn cửa sổ, :vlax-true = chờ xong
     (vlax-release-object sh)
     (setq kq (sn:doc-sx ra))
     (cond
       ((or (null kq) (not (listp kq)))
        (sn:loi (strcat "Cầu nối không trả kết quả. Nhật ký: "
                        (sn:cat-dong (vl-string-left-trim " " (sn:neu (sn:doc-van-ban log) "(trống)"))))))
       (T
        (if (and lsp? (sn:get "ok" kq) (findfile lsp)) (setq kq (append kq (list (cons "_lsp" lsp)))))
        kq)))))

(defun sn:ap-lsp (kq / f r)                              ; nạp file vẽ do cầu nối sinh (nếu có)
  (if (setq f (sn:get "_lsp" kq))
    (progn
      (setq r (vl-catch-all-apply 'load (list f)))
      (if (vl-catch-all-error-p r)
        (progn (sn:bao (strcat "Lỗi khi vẽ vào bản vẽ: " (vl-catch-all-error-message r))) nil)
        T))))

(defun sn:ap-lsp-cho ()                                  ; nạp file vẽ đã hoãn trong lúc hộp thoại mở
  (if *sn-cho-lsp*
    (progn (sn:ap-lsp (list (cons "_lsp" *sn-cho-lsp*))) (setq *sn-cho-lsp* nil))))

(defun sn:chay-ve (lenh args / kq)                       ; chạy rồi vẽ ngay, báo kết quả
  (setq kq (sn:chay lenh args T))
  (if (sn:get "ok" kq)
    (progn (sn:ap-lsp kq) (if (sn:get "thong_bao" kq) (sn:bao (sn:get "thong_bao" kq))))
    (sn:bao (strcat "Không thực hiện được: " (sn:neu (sn:get "thong_bao" kq) "lỗi không rõ"))))
  kq)

(defun sn:chay-duoc-p (kq)                               ; cầu nối ĐÃ chạy verb (kể cả mã thoát ≥ 2: ok = nil nhưng vẫn có văn bản)
  (and kq (sn:get "van_ban" (sn:get "du_lieu" kq)) T))

(defun sn:in-chay (kq / du vb)                           ; in kết quả của lệnh `chay` (verb)
  (setq du (sn:get "du_lieu" kq) vb (if du (sn:get "van_ban" du)))
  (cond
    ((and (null vb) (not (sn:get "ok" kq)))
     (sn:bao (strcat "Không chạy được: " (sn:neu (sn:get "thong_bao" kq) "lỗi không rõ"))))
    (T
     (if vb (foreach d (sn:chia (sn:thay vb "\r" "") "\n") (prompt (strcat "\n  " d))))
     (sn:bao (strcat "[mã thoát " (sn:vs (sn:get "ma_thoat" du)) "]")))))

;;; ===========================================================================================
;;; 5. DẤU TRUY VẾT (XDATA "SANNEN") — đọc nhãn, xóa kết quả cũ
;;; ===========================================================================================
(defun sn:xd-chuoi (e / d)                               ; XDATA SANNEN của một đối tượng → danh sách chuỗi
  (setq d (assoc -3 (entget e '("SANNEN"))))
  (if d (mapcar 'cdr (cdr (cadr d)))))

(defun sn:xd-get (xd khoa / r)                           ; giá trị của "khoa=giá trị" trong phần phụ (sau 4 ô đầu)
  (foreach s (cddddr xd)
    (if (and (null r) (= (substr s 1 (1+ (strlen khoa))) (strcat khoa "=")))
      (setq r (substr s (+ (strlen khoa) 2)))))
  r)

(defun sn:xoa-ket-qua (lo dot loai / ss i e xd n)       ; xóa kết quả SN của ĐÚNG lô này (RULES 5)
  (setq n 0)
  (if (setq ss (ssget "X" '((-3 ("SANNEN")))))
    (repeat (setq i (sslength ss))
      (setq e (ssname ss (setq i (1- i)))
            xd (sn:xd-chuoi e))
      (if (and xd (>= (length xd) 4) (= (car xd) lo)
               (or (null dot) (= (cadr xd) (itoa dot)))
               (or (null loai) (member (nth 3 xd) loai)))
        (progn (entdel e) (setq n (1+ n))))))
  n)

(defun sn:nhan-dinh (e / xd z)                           ; TEXT nhãn đỉnh → (mã bề_mặt z tên_đối_tượng) hoặc nil
  (setq xd (sn:xd-chuoi e))
  (if (and xd (>= (length xd) 4) (= (nth 3 xd) "nhan_dinh") (sn:xd-get xd "ma") (sn:xd-get xd "be_mat")
           (setq z (distof (cdr (assoc 1 (entget e))) 2)))
    (list (sn:xd-get xd "ma") (sn:xd-get xd "be_mat") z e)))

(defun sn:nhan-dinh-ds (lo ss / i it r)                  ; mọi nhãn đỉnh (moc/do) của lô `lo`; ss nil = cả bản vẽ
  (if (null ss) (setq ss (ssget "X" '((0 . "TEXT") (-3 ("SANNEN"))))))
  (if ss
    (repeat (setq i (sslength ss))
      (setq it (sn:nhan-dinh (ssname ss (setq i (1- i)))))
      (if (and it (member (cadr it) '("moc" "do")) (= (car (sn:xd-chuoi (cadddr it))) lo))
        (setq r (cons it r)))))
  (reverse r))

;;; ===========================================================================================
;;; 6. XUẤT CSV CHO LÕI
;;; ===========================================================================================
(defun sn:csv-nhan (f ds / txt)                          ; ma,be_mat,z — cho `dong-bo`
  (setq txt "ma,be_mat,z\n")
  (foreach i ds (setq txt (strcat txt (car i) "," (cadr i) "," (rtos (caddr i) 2 4) "\n")))
  (sn:ghi-van-ban f txt))

(defun sn:csv-hieuchinh (f ds be-mat ham-z ly-do / txt)  ; ma,z,be_mat,ly_do — cho `hieuchinh-nhieu`
  ;; ham-z: hàm (z-cũ) → z-mới. Chỉ lấy đỉnh thuộc `be-mat`. Dấu phẩy/nháy trong lý do bị thay để CSV không vỡ.
  (setq txt "ma,z,be_mat,ly_do\n")
  (setq ly-do (sn:thay (sn:thay (if ly-do ly-do "") "," ";") "\"" "'"))
  (foreach i ds
    (if (= (cadr i) be-mat)
      (setq txt (strcat txt (car i) "," (rtos (apply ham-z (list (caddr i))) 2 4) "," be-mat "," ly-do "\n"))))
  (sn:ghi-van-ban f txt))

;;; ===========================================================================================
;;; 7. TOÁN NHỎ CHO HỘP THOẠI LƯỚI
;;; ===========================================================================================
(defun sn:so-o (dai kt)                                  ; ceil(dai/kt) — số ô cần để phủ `dai`
  (max 1 (1+ (fix (- (/ dai kt) 1e-9)))))

(defun sn:mau-kt (n kt) (strcat (itoa n) "x" (sn:g kt)))   ; (5 20.0) → "5x20"

(defun sn:ma-o->ij (ma / g)                              ; "O03-02" → (3 2)
  (if (and ma (setq g (vl-string-search "-" ma)))
    (list (atoi (substr ma 2 (1- g))) (atoi (substr ma (+ g 2))))))

(defun sn:bbox (e / d tp pts xs ys o mn mx)              ; hộp bao của đối tượng → ((x1 y1) (x2 y2))
  ;; Ưu tiên đọc thẳng toạ độ đỉnh (chạy cả khi không có COM, vd accoreconsole); COM chỉ là dự phòng.
  (setq d (entget e) tp (cdr (assoc 0 d)))
  (cond
    ((= tp "LWPOLYLINE") (foreach i d (if (= (car i) 10) (setq pts (cons (cdr i) pts)))))
    ((= tp "LINE") (setq pts (list (cdr (assoc 10 d)) (cdr (assoc 11 d)))))
    ((= tp "POLYLINE")
     (setq e (entnext e))
     (while (and e (= (cdr (assoc 0 (entget e))) "VERTEX"))
       (if (/= (logand 192 (cdr (assoc 70 (entget e)))) 128)    ; bỏ bản ghi MẶT của polyface (cờ 128, toạ độ giả 0,0,0); đỉnh polyface = 192
         (setq pts (cons (cdr (assoc 10 (entget e))) pts)))
       (setq e (entnext e)))))
  (cond
    (pts
     (setq xs (mapcar 'car pts) ys (mapcar 'cadr pts))
     (list (list (apply 'min xs) (apply 'min ys)) (list (apply 'max xs) (apply 'max ys))))
    (T
     (setq o (vlax-ename->vla-object e))
     (vla-getboundingbox o 'mn 'mx)
     (list (vlax-safearray->list mn) (vlax-safearray->list mx)))))

(defun sn:o-tai (p / kq)                                 ; ô lưới chứa điểm p → alist hoặc nil (đã báo lỗi)
  (setq kq (sn:chay "o-tai" (strcat "--e " (rtos (car p) 2 4) " --n " (rtos (cadr p) 2 4)) nil))
  (if (sn:get "ok" kq)
    (sn:get "du_lieu" kq)
    (progn (sn:bao (strcat "Không xác định được ô: " (sn:neu (sn:get "thong_bao" kq) "?"))) nil)))

;;; ===========================================================================================
;;; 8. HỘP THOẠI — khung chung
;;; ===========================================================================================
(defun sn:dcl-file ( / d f)
  (setq d (sn:cfg "lisp"))
  (cond ((and d (findfile (setq f (strcat d "\\sannen.dcl")))) (findfile f))
        (T (findfile "sannen.dcl"))))

(defun sn:vn (khoa chu)                                  ; đặt chữ CÓ DẤU cho ô chữ/nút (DCL viết không dấu)
  (vl-catch-all-apply 'set_tile (list khoa chu)))

(defun sn:vn-ds (ds)                                     ; ds = (("khoá" . "chữ có dấu") ...) — đặt hàng loạt
  (foreach i ds (sn:vn (car i) (cdr i))))

(defun sn:vn-dong (khoas chu w / ds i n)                 ; chữ dài → nhiều ô text xếp dọc, tự ngắt dòng (không bị cắt cụt)
  (setq ds (sn:wrap (if chu chu "") w) i 0 n (length khoas))
  (foreach k khoas
    (sn:vn k (cond ((>= i n) "")
                   ((and (= i (1- n)) (> (length ds) n)) (strcat (nth i ds) " …"))   ; quá dài: dòng cuối có dấu lược
                   ((< i (length ds)) (nth i ds))
                   (T "")))
    (setq i (1+ i))))

(defun sn:tt (chu)                                       ; trạng thái ở chân hộp thoại: tối đa 3 dòng
  (sn:vn-dong '("t_tt" "t_tt2" "t_tt3") chu 56))

(defun sn:an (fn / r)                                    ; bọc callback: lỗi hiện ở dòng trạng thái, không rơi vào debugger
  (setq r (vl-catch-all-apply fn nil))
  (if (vl-catch-all-error-p r) (sn:tt (strcat "Lỗi: " (vl-catch-all-error-message r))))
  (princ))

(defun sn:mo-dlg (ten fn-khoi / f id kq)                 ; mở hộp thoại `ten`, chạy fn-khoi, trả mã done_dialog
  (cond
    ((not (setq f (sn:dcl-file))) (sn:bao "Không thấy sannen.dcl (đặt cạnh sannen.lsp hoặc khai lisp= trong sannen.cfg).") nil)
    ((or (null (setq id (load_dialog f))) (< id 1)) (sn:bao "Không nạp được sannen.dcl.") nil)
    (T
     (if (new_dialog ten id)
       (progn (apply fn-khoi nil) (setq kq (start_dialog)))
       (sn:bao (strcat "Không mở được hộp thoại " ten ".")))
     (unload_dialog id)
     kq)))

(defun sn:chay-lenh (ten fn / cmdecho osm r m)           ; bọc mọi lệnh: giữ biến hệ thống, bắt lỗi, lỗi tiếng Việt
  (setq cmdecho (getvar "CMDECHO") osm (getvar "OSMODE") *sn-da-bao-osnap* nil)
  (setvar "CMDECHO" 0)
  (setq r (vl-catch-all-apply fn nil))
  (setvar "CMDECHO" cmdecho)
  (setvar "OSMODE" osm)
  (if (vl-catch-all-error-p r)
    (progn
      (setq m (vl-catch-all-error-message r))
      (if (not (wcmatch (strcase m) "*QUIT*,*CANCEL*,*CANCELLED*"))
        (sn:bao (strcat ten ": lỗi — " m)))))
  (princ))

;;; ---- CHỌN ĐIỂM KHÔNG BỊ OSNAP TREO -------------------------------------------------------------
;;; Osnap Intersection trên đám đối tượng 3D dày (hàng chục nghìn mặt) báo "Too many objects selected for INTERSECT".
;;; Mọi lần chọn điểm trong menu đi qua sn:lay-diem: bật bit 16384 của OSMODE (osnap TẠM tắt, vẫn giữ các chế độ cũ),
;;; chọn điểm, rồi khôi phục NGUYÊN GIÁ TRỊ CŨ — kể cả khi người dùng ESC (lỗi bị vl-catch-all-apply bắt).
(setq *sn-da-bao-osnap* nil)
(defun sn:lay-diem (tieu base / osm r)
  (setq osm (getvar "OSMODE"))
  (setvar "OSMODE" (logior osm 16384))
  (if (null *sn-da-bao-osnap*)
    (progn (prompt "\n(đã tạm tắt osnap khi chọn điểm — sẽ khôi phục ngay sau đó)") (setq *sn-da-bao-osnap* T)))
  (setq r (vl-catch-all-apply 'getpoint (if base (list base tieu) (list tieu))))
  (setvar "OSMODE" osm)
  (if (vl-catch-all-error-p r) nil r))

;;; ===========================================================================================
;;; 9. LÔ & TRẠNG THÁI
;;; ===========================================================================================
(defun sn:l-lot ( / f dir)
  (setq f (getfiled "Chọn lot.yaml của lô cần làm việc" (sn:neu (sn:cfg "lot") "") "yaml;yml" 0))
  (if f
    (progn
      (setq dir (vl-filename-directory f))
      (cond ((findfile (strcat dir "\\lot.yaml"))
             (sn:ghi-cfg "lot" dir)
             (sn:bao (strcat "Đã chọn lô: " dir " (mã lô " (sn:neu (sn:ma-lo) "?") ")")))
            (T (sn:bao "Thư mục đó không có lot.yaml."))))))
(defun c:SN_LOT () (sn:chay-lenh "SN_LOT" 'sn:l-lot))

(defun sn:l-trangthai ( / kq)
  (if (sn:can-lot)
    (progn
      (setq kq (sn:chay "trang-thai" "" nil))
      (if (sn:get "ok" kq)
        (progn (sn:bao (strcat "TRẠNG THÁI LÔ " (sn:neu (sn:ma-lo) ""))) (sn:in (sn:get "du_lieu" kq) 2))
        (sn:bao (strcat "Không đọc được trạng thái: " (sn:neu (sn:get "thong_bao" kq) "?")))))))
(defun c:SN_TRANGTHAI () (sn:chay-lenh "SN_TRANGTHAI" 'sn:l-trangthai))

;;; ===========================================================================================
;;; 10. CHẠY VERB CỦA LÕI (nhập, mặt, lô, lưới, tính, xuất) — xem trước rồi hỏi mới ghi
;;; ===========================================================================================
(defun sn:xac-nhan (cau mac-dinh-co / r)                 ; hỏi Yes/No; trả T nếu Yes
  (initget "Yes No")
  (setq r (getkword (strcat "\n" cau (if mac-dinh-co "[Yes/No] <Yes>: " "[Yes/No] <No>: "))))
  (cond ((null r) mac-dinh-co) ((= r "Yes") T) (T nil)))

(defun sn:ve ( / kq)                                     ; vẽ lại toàn bộ kết quả của lô
  (if (sn:can-lot) (setq kq (sn:chay-ve "ve" ""))) kq)
(defun c:SN_VE () (sn:chay-lenh "SN_VE" 'sn:ve))

(defun sn:l-verb (verb / kq them vb)
  (if (sn:can-lot)
    (progn
      (sn:bao (strcat "── " (strcase verb) " — XEM TRƯỚC (chưa ghi gì) ──"))
      (setq kq (sn:chay "chay" (strcat "--verb " verb " --them=" (sn:q "--preview")) nil))
      (sn:in-chay kq)
      (if (and (sn:chay-duoc-p kq) (sn:xac-nhan (strcat "Ghi thật `" verb "`? ") nil))
        (progn
          (setq them "")
          (if (and (= verb "tinh") (sn:xac-nhan "Quét ma trận phương án (--sweep)? " nil)) (setq them "--sweep"))
          (setq kq (sn:chay "chay" (strcat "--verb " verb (if (/= them "") (strcat " --them=" (sn:q them)) "")) nil))
          (sn:in-chay kq)
          ;; nhập Excel mới: lõi dừng chờ NGƯỜI xác nhận ánh xạ cột (RULES 7)
          (setq vb (sn:get "van_ban" (sn:get "du_lieu" kq)))
          (if (and (= verb "nhap") vb (vl-string-search "XÁC NHẬN" vb)
                   (sn:xac-nhan "Bạn đã soát ánh xạ cột đề xuất ở trên và đồng ý? " nil))
            (sn:in-chay (sn:chay "chay" (strcat "--verb nhap --them=" (sn:q "--xac-nhan-anh-xa")) nil)))
          (if (and (member verb '("mat" "lo" "luoi" "tinh")) (sn:get "ok" kq)    ; ok = mã thoát ≤ 1
                   (sn:xac-nhan "Vẽ lại kết quả vào bản vẽ? " T))
            (sn:ve)))))))
(defun c:SN_NHAP ()     (sn:chay-lenh "SN_NHAP"     '(lambda () (sn:l-verb "nhap"))))
(defun c:SN_MAT ()      (sn:chay-lenh "SN_MAT"      '(lambda () (sn:l-verb "mat"))))
(defun c:SN_LO ()       (sn:chay-lenh "SN_LO"       '(lambda () (sn:l-verb "lo"))))
(defun c:SN_LUOITINH () (sn:chay-lenh "SN_LUOITINH" '(lambda () (sn:l-verb "luoi"))))
(defun c:SN_TINH ()     (sn:chay-lenh "SN_TINH"     '(lambda () (sn:l-verb "tinh"))))
(defun c:SN_EXCEL ()    (sn:chay-lenh "SN_EXCEL"    '(lambda () (sn:l-verb "xuat"))))

(defun sn:l-xoa ( / lo n)
  (if (sn:can-lot)
    (progn
      (setq lo (sn:ma-lo))
      (if (and lo (sn:xac-nhan (strcat "Xóa MỌI đối tượng kết quả SN của lô " lo " trong bản vẽ này? ") nil))
        (sn:bao (strcat "Đã xóa " (itoa (sn:xoa-ket-qua lo nil nil)) " đối tượng kết quả."))))))
(defun c:SN_XOA () (sn:chay-lenh "SN_XOA" 'sn:l-xoa))


;;; ===========================================================================================
;;; 11. XEM 3D CỦA TIN — POLYFACE (một đối tượng/bề mặt) + VIEW "SN_TIN3D" + CHỈ HIỂN THỊ MẶT 3D
;;; ===========================================================================================
(setq *sn-t3d-bm* "2" *sn-t3d-iso* "1" *sn-t3d-bong* "1" *sn-t3d-chi3d* "0")   ; bm: 0 = mốc, 1 = đo, 2 = cả hai
(setq *sn-lop-an* nil)     ; tên các layer ĐÃ TẮT để xem riêng mặt 3D — "Khôi phục lớp" bật lại đúng danh sách này

(defun sn:lop-3d-p (ten) (wcmatch (strcase ten) "SN-3DF-*,SN-QC*"))

(defun sn:lop-bat (ten bat / r on)                       ; bật/tắt (ON/OFF, KHÔNG đóng băng, KHÔNG xóa) một layer; T nếu có đổi
  (if (and (tblsearch "LAYER" ten) (setq r (entget (tblobjname "LAYER" ten))))
    (progn
      (setq on (>= (cdr (assoc 62 r)) 0))
      (if (eq on (if bat T nil))
        nil
        (progn (entmod (subst (cons 62 (if bat (abs (cdr (assoc 62 r))) (- (abs (cdr (assoc 62 r)))))) (assoc 62 r) r)) T)))))

(defun sn:lop-dang-hien ( / d r cl)                      ; layer đang BẬT, không đóng băng, không phải xref/layer hiện hành/layer 3D của SN
  (setq cl (strcase (getvar "CLAYER")) d (tblnext "LAYER" T))
  (while d
    (if (and (>= (cdr (assoc 62 d)) 0)
             (zerop (logand 1 (cdr (assoc 70 d))))
             (not (vl-string-search "|" (cdr (assoc 2 d))))
             (not (sn:lop-3d-p (cdr (assoc 2 d))))
             (/= (strcase (cdr (assoc 2 d))) cl))
      (setq r (cons (cdr (assoc 2 d)) r)))
    (setq d (tblnext "LAYER")))
  (reverse r))

(defun sn:luu-lop-an ()                                  ; lưu danh sách vào CHÍNH bản vẽ (sống qua lần đóng/mở) — lỗi thì thôi, vẫn còn biến
  (vl-catch-all-apply 'vlax-ldata-put (list "SANNEN" "LOP_AN" (if *sn-lop-an* *sn-lop-an* ""))))

(defun sn:doc-lop-an ( / r)                              ; đọc danh sách layer đã ẩn (ưu tiên bản lưu trong bản vẽ)
  (setq r (vl-catch-all-apply 'vlax-ldata-get (list "SANNEN" "LOP_AN" "")))
  (if (and (not (vl-catch-all-error-p r)) (listp r) r (null (vl-remove-if 'sn:chuoi-p r)))
    (setq *sn-lop-an* r))
  *sn-lop-an*)

(defun sn:chi-hien-3d ( / n)                             ; tắt (OFF) mọi layer ngoài SN-3DF-*/SN-QC*; nhớ danh sách để khôi phục
  (sn:doc-lop-an)
  (setq n 0)
  (foreach l (sn:lop-dang-hien)
    (if (sn:lop-bat l nil)
      (progn (setq n (1+ n))
             (if (not (member l *sn-lop-an*)) (setq *sn-lop-an* (append *sn-lop-an* (list l)))))))
  (sn:luu-lop-an)
  (sn:thu '(lambda () (command "_.REGEN")))
  n)

(defun sn:khoi-phuc-lop ( / n)                           ; bật lại ĐÚNG những layer đã tắt ở trên (layer đã bị xóa thì bỏ qua)
  (sn:doc-lop-an)
  (setq n 0)
  (foreach l *sn-lop-an* (if (sn:lop-bat l T) (setq n (1+ n))))
  (setq *sn-lop-an* nil)
  (sn:luu-lop-an)
  (sn:thu '(lambda () (command "_.REGEN")))
  n)

(defun sn:t3d-khoi ( / n)
  (sn:vn-ds '(("t_ten" . "Xem bề mặt TIN dạng 3D (polyface)")
              ("t_tieu" . "Mỗi bề mặt là MỘT khối: chọn / ẩn / xóa một lần")
              ("n_bm" . "Bề mặt cần xem")
              ("n_iso" . "Đổi sang góc nhìn 3D (SW Isometric), phóng tới bề mặt, lưu view SN_TIN3D")
              ("n_bong" . "Tô bóng (Shaded with edges)")
              ("n_chi3d" . "Chỉ hiển thị mặt 3D (tạm tắt các lớp khác)")
              ("b_hien" . "Hiển thị") ("b_tat" . "Tắt 3D") ("b_khoiphuc" . "Khôi phục lớp")
              ("b_xem" . "Mở trình xem 3D (HTML)") ("b_dong" . "Đóng")))
  (start_list "p_bemat")
  (mapcar 'add_list '("Mặt mốc (tự nhiên, trước san lấp) — xanh lá" "Mặt đo (sau san lấp) — vàng" "Cả hai mặt"))
  (end_list)
  (set_tile "p_bemat" *sn-t3d-bm*) (set_tile "t_iso" *sn-t3d-iso*) (set_tile "t_bong" *sn-t3d-bong*)
  (set_tile "t_chi3d" *sn-t3d-chi3d*)
  (setq n (length (sn:doc-lop-an)))
  (sn:tt (if (> n 0)
           (strcat "Đang ẩn " (itoa n) " lớp để xem riêng mặt 3D — bấm Khôi phục lớp để hiện lại đúng các lớp đó.")
           "Mặt 3D tắt sẵn trong bản vẽ; nút Hiển thị sẽ vẽ (nếu chưa có), bật lớp, đổi góc nhìn và lưu view SN_TIN3D."))
  (action_tile "b_hien" "(sn:t3d-luu) (done_dialog 1)")
  (action_tile "b_tat" "(sn:t3d-luu) (done_dialog 2)")
  (action_tile "b_khoiphuc" "(sn:t3d-luu) (done_dialog 3)")
  (action_tile "b_xem" "(sn:t3d-luu) (done_dialog 4)")
  (action_tile "b_dong" "(done_dialog 0)"))

(defun sn:t3d-luu ()
  (setq *sn-t3d-bm* (get_tile "p_bemat") *sn-t3d-iso* (get_tile "t_iso") *sn-t3d-bong* (get_tile "t_bong")
        *sn-t3d-chi3d* (get_tile "t_chi3d")))

(defun sn:luu-view (ten)                                 ; lưu view hiện hành (-VIEW Save); trùng tên thì xóa bản cũ trước
  (if (tblsearch "VIEW" ten) (sn:thu (list 'lambda nil (list 'command "_.-VIEW" "_D" ten))))
  (sn:thu (list 'lambda nil (list 'command "_.-VIEW" "_S" ten))))

(defun sn:xem-3d (iso bong bm / ss loc)                  ; góc nhìn + zoom + view SN_TIN3D — gọi SAU khi hộp thoại đóng
  (if (= iso "1") (sn:thu '(lambda () (command "_.-VIEW" "_SWISO"))))
  (if (= bong "1") (sn:thu '(lambda () (command "_.VSCURRENT" "_E"))))      ; Shaded with Edges
  (setq loc (strcat (if (/= bm "do") "SN-3DF-MOC*," "") (if (/= bm "moc") "SN-3DF-DO*," "") "SN-QC*"))
  (setq ss (ssget "X" (list '(-3 ("SANNEN")) (cons 8 loc))))
  (if ss
    (sn:thu (list 'lambda nil (list 'command "_.ZOOM" "_O" ss "")))                 ; phóng vừa khít các khối polyface
    (sn:thu '(lambda () (command "_.ZOOM" "_E"))))
  (sn:luu-view "SN_TIN3D")
  (sn:bao "Đã lưu view \"SN_TIN3D\" — khôi phục bằng lệnh -VIEW → Restore → SN_TIN3D."))

(defun sn:l-tin3d ( / ma bm kq)
  (if (sn:can-lot)
    (progn
      (setq ma (sn:mo-dlg "sn_tin3d" 'sn:t3d-khoi))
      (cond
        ((= ma 1)
         (setq bm (cond ((= *sn-t3d-bm* "0") "moc") ((= *sn-t3d-bm* "1") "do") (T "ca-hai")))
         (setq kq (sn:chay-ve "tin3d" (strcat "--be-mat " bm " --dang polyface")))
         (if (sn:get "ok" kq)
           (progn
             (if (= *sn-t3d-chi3d* "1")
               (sn:bao (strcat "Đã tạm tắt " (itoa (sn:chi-hien-3d)) " lớp khác (chỉ ON/OFF, không đóng băng/xóa). "
                               "Hiện lại: SN_TIN3D → Khôi phục lớp.")))
             (sn:xem-3d *sn-t3d-iso* *sn-t3d-bong* (if (= bm "ca-hai") "ca" bm)))))
        ((= ma 2) (sn:chay-ve "tin3d-tat" ""))
        ((= ma 3) (sn:bao (strcat "Đã bật lại " (itoa (sn:khoi-phuc-lop)) " lớp.")))
        ((= ma 4) (sn:l-xem3d))))))
(defun c:SN_TIN3D () (sn:chay-lenh "SN_TIN3D" 'sn:l-tin3d))

;;; SN_XEM3D: lõi dựng trình xem 3D HTML (python -m sannen.cli xem3d --lot <lô> --mo) và mở bằng trình duyệt mặc định
(defun sn:l-xem3d ( / kq)
  (if (sn:can-lot)
    (progn
      (sn:bao "Đang dựng trình xem 3D (HTML) bằng lõi…")
      (setq kq (sn:chay "xem3d" "" nil))
      (if (sn:get "ok" kq)
        (sn:bao (strcat "Đã mở trình xem 3D: " (sn:neu (sn:get "file" (sn:get "du_lieu" kq)) "(trình duyệt mặc định)")))
        (sn:bao (strcat "Không mở được trình xem 3D: " (sn:neu (sn:get "thong_bao" kq) "lỗi không rõ")))))))
(defun c:SN_XEM3D () (sn:chay-lenh "SN_XEM3D" 'sn:l-xem3d))

;;; ===========================================================================================
;;; 12. HIỆU CHỈNH LƯỚI  (hộp thoại sn_luoi + lệnh nhanh)
;;; ===========================================================================================
(setq *sn-lt* nil)         ; alist trạng thái lưới đang hiện trong hộp thoại
(setq *sn-lt-nhap* nil)    ; alist các ô người đã gõ trong hộp thoại (chuỗi)
(setq *sn-lt-moi-goc* nil) ; gốc lưới mới do "Chọn vùng…" (E N) — dùng khi Áp dụng

(defun sn:lt-nhap (d)                                    ; nhận kết quả luoi-doc (hoặc luoi-sua có khoá "luoi")
  (if (and d (assoc "luoi" d)) (setq d (sn:get "luoi" d)))
  (if d (setq *sn-lt* d)))

(defun sn:lt-dien ( / g ds)                              ; đổ *sn-lt* ra các ô của hộp thoại
  (setq g (sn:get "goc_luoi" *sn-lt*))
  (set_tile "e_kt"   (sn:g (sn:neu (sn:get "kich_thuoc" *sn-lt*) 20.0)))
  (set_tile "e_goc"  (sn:g (sn:neu (sn:get "goc_xoay_do" *sn-lt*) 0.0)))
  (set_tile "e_cot"  (sn:neu (sn:get "cot" *sn-lt*) ""))
  (set_tile "e_hang" (sn:neu (sn:get "hang" *sn-lt*) ""))
  (set_tile "e_ns"   (sn:g (sn:neu (sn:get "ngoai_suy_m" *sn-lt*) 0.0)))
  (start_list "p_kieu") (mapcar 'add_list '("diem_gan_nhat" "gan_nhat" "mat_phang")) (end_list)
  (set_tile "p_kieu" (itoa (max 0 (sn:neu (vl-position (sn:get "ngoai_suy_kieu" *sn-lt*) '("diem_gan_nhat" "gan_nhat" "mat_phang")) 0))))
  (sn:vn "t_gocluoi"
         (strcat "Gốc lưới (E, N): "
                 (if *sn-lt-moi-goc*
                   (strcat (rtos (car *sn-lt-moi-goc*) 2 3) ", " (rtos (cadr *sn-lt-moi-goc*) 2 3) "  [MỚI — chưa áp dụng]")
                   (if g (strcat (rtos (car g) 2 3) ", " (rtos (cadr g) 2 3)) "chưa có lưới"))))
  (sn:vn-dong '("t_tieu" "t_tieu2")
         (strcat (itoa (fix (sn:neu (sn:get "nx" *sn-lt*) 0))) " cột × " (itoa (fix (sn:neu (sn:get "ny" *sn-lt*) 0)))
                 " hàng — tổng diện tích ô " (rtos (sn:neu (sn:get "dt_o" *sn-lt*) 0.0) 2 2) " m² / diện tích lô "
                 (rtos (sn:neu (sn:get "dt_lo" *sn-lt*) 0.0) 2 2) " m²")
         64))

(defun sn:dat (khoa gt lst)                              ; đặt/cập nhật một khoá trong alist
  (if (assoc khoa lst)
    (subst (cons khoa gt) (assoc khoa lst) lst)
    (append lst (list (cons khoa gt)))))

(defun sn:lt-luu ()                                      ; đọc các ô vào biến (trước khi đóng hoặc gọi lõi)
  (setq *sn-lt-nhap*
        (list (cons "kt" (get_tile "e_kt")) (cons "goc" (get_tile "e_goc")) (cons "cot" (get_tile "e_cot"))
              (cons "hang" (get_tile "e_hang")) (cons "ns" (get_tile "e_ns"))
              (cons "kieu" (nth (atoi (get_tile "p_kieu")) '("diem_gan_nhat" "gan_nhat" "mat_phang")))
              (cons "chiso" (get_tile "e_chiso")) (cons "ktdoi" (get_tile "e_ktdoi")))))

(defun sn:lt-xu-ly (kq / cb)                             ; xử lý kết quả luoi-sua: làm mới ô, hoãn việc vẽ
  (cond
    ((not (sn:get "ok" kq)) (sn:tt (strcat "Không thực hiện được: " (sn:neu (sn:get "thong_bao" kq) "?"))))
    (T
     (sn:lt-nhap (sn:get "du_lieu" kq))
     (setq *sn-lt-moi-goc* nil)
     (sn:lt-dien)
     (if (sn:get "_lsp" kq) (setq *sn-cho-lsp* (sn:get "_lsp" kq)))
     (setq cb (sn:get "canh_bao" (sn:get "du_lieu" kq)))
     (sn:tt (strcat "Đã áp dụng và tính lại." (if (and cb (listp cb) cb) (strcat " Cảnh báo: " (sn:cat-dong (sn:vs cb))) ""))))))

(defun sn:lt-lenh (lenh them / kq)                       ; một lệnh luoi-sua, KHÔNG đóng hộp thoại
  (sn:lt-luu)
  (setq kq (sn:chay "luoi-sua" (strcat "--lenh " lenh " " them " --ly-do=" (sn:q "Hộp thoại SN_LUOI")) T))
  (sn:lt-xu-ly kq))

(defun sn:lt-chiso-ktdoi ( / c k)
  (setq c (atoi (sn:get "chiso" *sn-lt-nhap*)) k (sn:so (sn:get "ktdoi" *sn-lt-nhap*)))
  (list c k))

(defun sn:cb-doi-cot ()   (sn:lt-luu) (sn:lt-lenh "doi_cot"   (strcat "--chi-so " (itoa (car (sn:lt-chiso-ktdoi))) " --kich-thuoc " (sn:g (sn:neu (cadr (sn:lt-chiso-ktdoi)) 0)))))
(defun sn:cb-doi-hang ()  (sn:lt-luu) (sn:lt-lenh "doi_hang"  (strcat "--chi-so " (itoa (car (sn:lt-chiso-ktdoi))) " --kich-thuoc " (sn:g (sn:neu (cadr (sn:lt-chiso-ktdoi)) 0)))))
(defun sn:cb-chen-cot ()  (sn:lt-luu) (sn:lt-lenh "chen_cot"  (strcat "--sau " (itoa (car (sn:lt-chiso-ktdoi))) " --kich-thuoc " (sn:g (sn:neu (cadr (sn:lt-chiso-ktdoi)) 0)))))
(defun sn:cb-chen-hang () (sn:lt-luu) (sn:lt-lenh "chen_hang" (strcat "--sau " (itoa (car (sn:lt-chiso-ktdoi))) " --kich-thuoc " (sn:g (sn:neu (cadr (sn:lt-chiso-ktdoi)) 0)))))
(defun sn:cb-xoa-cot ()   (sn:lt-luu) (sn:lt-lenh "xoa_cot"   (strcat "--chi-so " (itoa (car (sn:lt-chiso-ktdoi))))))
(defun sn:cb-xoa-hang ()  (sn:lt-luu) (sn:lt-lenh "xoa_hang"  (strcat "--chi-so " (itoa (car (sn:lt-chiso-ktdoi))))))

(defun sn:cb-ap-dung ( / n kt goc ns a)                  ; "Áp dụng" = luoi-sua dat với mọi ô của hộp thoại
  (sn:lt-luu)
  (setq n *sn-lt-nhap* kt (sn:so (sn:get "kt" n)) goc (sn:so (sn:get "goc" n)) ns (sn:so (sn:get "ns" n)))
  (cond
    ((or (null kt) (<= kt 0)) (sn:tt "Kích thước ô phải là số dương."))
    ((null goc) (sn:tt "Góc xoay phải là số (độ)."))
    ((or (null ns) (< ns 0)) (sn:tt "Khoảng bù dữ liệu thiếu phải là số ≥ 0."))
    (T
     (setq a (strcat "--o " (sn:g kt) " --goc=" (sn:g goc) " --ngoai-suy " (sn:g ns) " --kieu " (sn:get "kieu" n)
                     " --cot=" (sn:q (sn:get "cot" n)) " --hang=" (sn:q (sn:get "hang" n))
                     (if *sn-lt-moi-goc* (strcat " --goc-luoi " (sn:en *sn-lt-moi-goc*)) "")))
     (sn:lt-lenh "dat" a))))

(defun sn:cb-ve-lot ( / kq)
  (sn:lt-luu)
  (setq kq (sn:chay "luoi-ve-lai-lot-yaml" "" T))
  (sn:lt-xu-ly kq))

(defun sn:cb-dong-ma (ma / n v)                           ; các nút đóng tạm để pick trên bản vẽ — GIỮ lại những gì đã gõ
  (sn:lt-luu)
  (setq n *sn-lt-nhap*)
  (if (setq v (sn:so (sn:get "kt" n)))   (setq *sn-lt* (sn:dat "kich_thuoc" v *sn-lt*)))
  (if (setq v (sn:so (sn:get "goc" n)))  (setq *sn-lt* (sn:dat "goc_xoay_do" v *sn-lt*)))
  (if (setq v (sn:so (sn:get "ns" n)))   (setq *sn-lt* (sn:dat "ngoai_suy_m" v *sn-lt*)))
  (setq *sn-lt* (sn:dat "cot" (sn:get "cot" n) *sn-lt*))
  (setq *sn-lt* (sn:dat "hang" (sn:get "hang" n) *sn-lt*))
  (setq *sn-lt* (sn:dat "ngoai_suy_kieu" (sn:get "kieu" n) *sn-lt*))
  (done_dialog ma))

(defun sn:lt-khoi ()
  (sn:vn-ds '(("t_ten" . "Hiệu chỉnh lưới ô vuông")
              ("t_nhom1" . "Thông số lưới") ("t_nhom2" . "Hàng / cột (chỉ số tính từ 1)")
              ("n_kt" . "Kích thước ô (m)") ("n_goc" . "Góc xoay (độ)")
              ("n_cot" . "Cột (Số×KT, …)") ("n_hang" . "Hàng (Số×KT, …)")
              ("n_ns" . "Bù dữ liệu thiếu trong (m)") ("n_kieu" . "Kiểu")
              ("n_chiso" . "Chỉ số") ("n_ktdoi" . "Kích thước (m)")
              ("b_doi_cot" . "Đổi KT cột") ("b_doi_hang" . "Đổi KT hàng") ("b_chen_cot" . "Chèn sau cột")
              ("b_chen_hang" . "Chèn sau hàng") ("b_xoa_cot" . "Xóa cột") ("b_xoa_hang" . "Xóa hàng")
              ("b_di_chuyen" . "Di chuyển lưới…") ("b_xoay" . "Xoay lưới…") ("b_vung" . "Chọn vùng…")
              ("b_ve_lot" . "Về lot.yaml") ("b_ap_dung" . "Áp dụng") ("b_dong" . "Đóng")))
  (sn:lt-dien)
  (set_tile "e_chiso" "1") (set_tile "e_ktdoi" "20")
  (sn:tt "Cột/Hàng nhập dạng Số×KT, ví dụ 10x20,5x15. Mọi thay đổi được ghi vào luoi_tuy_chinh.yaml và nhật ký quyết định decisions.md.")
  (action_tile "b_doi_cot"   "(sn:an 'sn:cb-doi-cot)")
  (action_tile "b_doi_hang"  "(sn:an 'sn:cb-doi-hang)")
  (action_tile "b_chen_cot"  "(sn:an 'sn:cb-chen-cot)")
  (action_tile "b_chen_hang" "(sn:an 'sn:cb-chen-hang)")
  (action_tile "b_xoa_cot"   "(sn:an 'sn:cb-xoa-cot)")
  (action_tile "b_xoa_hang"  "(sn:an 'sn:cb-xoa-hang)")
  (action_tile "b_ap_dung"   "(sn:an 'sn:cb-ap-dung)")
  (action_tile "b_ve_lot"    "(sn:an 'sn:cb-ve-lot)")
  (action_tile "b_di_chuyen" "(sn:cb-dong-ma 2)")
  (action_tile "b_xoay"      "(sn:cb-dong-ma 3)")
  (action_tile "b_vung"      "(sn:cb-dong-ma 4)")
  (action_tile "b_dong"      "(done_dialog 0)"))

(defun sn:lt-di-chuyen ( / p1 p2 kq)                     ; như lệnh Move: điểm cơ sở → điểm mới
  (if (and (setq p1 (sn:lay-diem "\nXác định điểm cơ sở: " nil)) (setq p2 (sn:lay-diem "\nĐiểm mới: " p1)))
    (progn
      (setq kq (sn:chay "luoi-sua" (strcat "--lenh di_chuyen --dx=" (rtos (- (car p2) (car p1)) 2 4)
                                           " --dy=" (rtos (- (cadr p2) (cadr p1)) 2 4)
                                           " --ly-do=" (sn:q "Di chuyển lưới trong CAD")) T))
      (sn:lt-nhap (sn:get "du_lieu" kq))
      (if (sn:get "_lsp" kq) (setq *sn-cho-lsp* (sn:get "_lsp" kq)))
      (if (not (sn:get "ok" kq)) (sn:bao (strcat "Không di chuyển được: " (sn:neu (sn:get "thong_bao" kq) "?")))))))

(defun sn:lt-xoay ( / g kq)
  (setq g (getreal (strcat "\nGóc nghiêng lưới (độ) <" (sn:g (sn:neu (sn:get "goc_xoay_do" *sn-lt*) 0.0)) ">: ")))
  (if g
    (progn
      (setq kq (sn:chay "luoi-sua" (strcat "--lenh xoay --goc=" (sn:g g) " --ly-do=" (sn:q "Xoay lưới trong CAD")) T))
      (sn:lt-nhap (sn:get "du_lieu" kq))
      (if (sn:get "_lsp" kq) (setq *sn-cho-lsp* (sn:get "_lsp" kq)))
      (if (not (sn:get "ok" kq)) (sn:bao (strcat "Không xoay được: " (sn:neu (sn:get "thong_bao" kq) "?")))))))

(defun sn:lt-chon-vung ( / e bb kt w h nx ny)            ; như SNVN: chọn vùng → tự tính số cột/hàng
  (if (setq e (car (entsel "\nChọn đa tuyến / hình chữ nhật bao vùng tính đào đắp: ")))
    (progn
      (setq bb (sn:bbox e)
            kt (sn:neu (sn:so (sn:get "kt" *sn-lt-nhap*)) 20.0)
            w (- (car (cadr bb)) (car (car bb))) h (- (cadr (cadr bb)) (cadr (car bb)))
            nx (sn:so-o w kt) ny (sn:so-o h kt))
      (setq *sn-lt* (sn:dat "cot" (sn:mau-kt nx kt) *sn-lt*))
      (setq *sn-lt* (sn:dat "hang" (sn:mau-kt ny kt) *sn-lt*))
      (setq *sn-lt-moi-goc* (list (car (car bb)) (cadr (car bb))))
      (sn:bao (strcat "Vùng " (rtos w 2 2) " × " (rtos h 2 2) " m → " (itoa nx) " cột × " (itoa ny) " hàng ô " (sn:g kt)
                      " m. Bấm Áp dụng để đặt lưới.")))))

(defun sn:l-luoi ( / kq ma)
  (if (sn:can-lot)
    (progn
      (setq kq (sn:chay "luoi-doc" "" nil))
      (cond
        ((not (sn:get "ok" kq))
         (sn:bao (strcat "Chưa có lưới (" (sn:neu (sn:get "thong_bao" kq) "?") "). Chạy SN_LUOITINH hoặc xem lot.yaml.")))
        (T
         (setq *sn-lt* nil *sn-lt-moi-goc* nil *sn-cho-lsp* nil)
         (sn:lt-nhap (sn:get "du_lieu" kq))
         (setq *sn-lt-nhap* (list (cons "kt" (sn:g (sn:neu (sn:get "kich_thuoc" *sn-lt*) 20.0))) (cons "goc" "0")
                                  (cons "cot" "") (cons "hang" "") (cons "ns" "0") (cons "kieu" "diem_gan_nhat")
                                  (cons "chiso" "1") (cons "ktdoi" "20")))
         (setq ma 2)
         (while (member ma '(2 3 4))
           (setq ma (sn:mo-dlg "sn_luoi" 'sn:lt-khoi))
           (cond ((= ma 2) (sn:lt-di-chuyen))
                 ((= ma 3) (sn:lt-xoay))
                 ((= ma 4) (sn:lt-chon-vung))))
         (sn:ap-lsp-cho))))))
(defun c:SN_LUOI () (sn:chay-lenh "SN_LUOI" 'sn:l-luoi))

;;; ---- lệnh nhanh không cần hộp thoại: SN_DOICOT, SN_CHENCOT, SN_XOACOT, SN_DOIHANG, SN_CHENHANG, SN_XOAHANG ...
(defun sn:nhanh-o (tieu / p o ij)                        ; chọn điểm trong một ô → (cột hàng)
  (if (setq p (sn:lay-diem tieu nil))
    (if (setq o (sn:o-tai p)) (setq ij (sn:ma-o->ij (sn:get "ma" o))))
    nil)
  ij)

(defun sn:nhanh (lenh cot? kieu / ij k a i)              ; kieu: "doi" (hỏi KT), "chen" (hỏi KT), "xoa"
  (if (sn:can-lot)
    (if (setq ij (sn:nhanh-o (if cot? "\nChọn điểm trong ô thuộc CỘT cần xử lý: " "\nChọn điểm trong ô thuộc HÀNG cần xử lý: ")))
      (progn
        (setq i (if cot? (car ij) (cadr ij)))
        (if (/= kieu "xoa")
          (setq k (getdist (strcat "\n" (if cot? "Kích thước cột" "Kích thước hàng") " (m): "))))
        (if (or (= kieu "xoa") k)
          (progn
            (setq a (cond ((= kieu "xoa")  (strcat "--chi-so " (itoa i)))
                          ((= kieu "doi")  (strcat "--chi-so " (itoa i) " --kich-thuoc " (sn:g k)))
                          (T               (strcat "--sau " (itoa i) " --kich-thuoc " (sn:g k)))))
            (sn:chay-ve "luoi-sua" (strcat "--lenh " lenh " " a " --ly-do=" (sn:q "Lệnh nhanh trong CAD")))))))))
(defun c:SN_DOICOT ()   (sn:chay-lenh "SN_DOICOT"   '(lambda () (sn:nhanh "doi_cot" T "doi"))))
(defun c:SN_CHENCOT ()  (sn:chay-lenh "SN_CHENCOT"  '(lambda () (sn:nhanh "chen_cot" T "chen"))))
(defun c:SN_XOACOT ()   (sn:chay-lenh "SN_XOACOT"   '(lambda () (sn:nhanh "xoa_cot" T "xoa"))))
(defun c:SN_DOIHANG ()  (sn:chay-lenh "SN_DOIHANG"  '(lambda () (sn:nhanh "doi_hang" nil "doi"))))
(defun c:SN_CHENHANG () (sn:chay-lenh "SN_CHENHANG" '(lambda () (sn:nhanh "chen_hang" nil "chen"))))
(defun c:SN_XOAHANG ()  (sn:chay-lenh "SN_XOAHANG"  '(lambda () (sn:nhanh "xoa_hang" nil "xoa"))))

(defun sn:l-dichluoi ( / p1 p2)
  (if (sn:can-lot)
    (if (and (setq p1 (sn:lay-diem "\nXác định điểm cơ sở: " nil)) (setq p2 (sn:lay-diem "\nĐiểm mới: " p1)))
      (sn:chay-ve "luoi-sua" (strcat "--lenh di_chuyen --dx=" (rtos (- (car p2) (car p1)) 2 4)
                                     " --dy=" (rtos (- (cadr p2) (cadr p1)) 2 4) " --ly-do=" (sn:q "Di chuyển lưới (lệnh nhanh)"))))))
(defun c:SN_DICHLUOI () (sn:chay-lenh "SN_DICHLUOI" 'sn:l-dichluoi))

(defun sn:l-xoayluoi ( / g)
  (if (sn:can-lot)
    (if (setq g (getreal "\nNhập góc nghiêng lưới (độ): "))
      (sn:chay-ve "luoi-sua" (strcat "--lenh xoay --goc=" (sn:g g) " --ly-do=" (sn:q "Xoay lưới (lệnh nhanh)"))))))
(defun c:SN_XOAYLUOI () (sn:chay-lenh "SN_XOAYLUOI" 'sn:l-xoayluoi))

;;; ===========================================================================================
;;; 13. HIỆU CHỈNH CAO ĐỘ ĐỈNH LƯỚI  (SN_CAPDO, SN_NANGCD, SN_SUADINH)
;;; ===========================================================================================
(setq *sn-cd-ds* nil *sn-cd-che* "0" *sn-cd-gt* "0" *sn-cd-bm* "0" *sn-cd-lydo* "")   ; che: 0 = nâng/hạ, 1 = đặt; bm: 0 = đo, 1 = mốc

(defun sn:cd-ap-dung (ds be-mat ham-z ly-do / csv kq)    ; ghi CSV rồi nhờ lõi áp dụng nhiều đỉnh + vẽ lại nhãn
  (setq csv (strcat (sn:tmp) "\\sn_hieuchinh.csv"))
  (sn:csv-hieuchinh csv ds be-mat ham-z ly-do)
  (setq kq (sn:chay-ve "hieuchinh-nhieu" (strcat "--tu-file " (sn:q csv) " --ly-do=" (sn:q ly-do))))
  kq)

(defun sn:cd-chon ( / ss ds)                             ; chọn nhãn đỉnh trên bản vẽ
  (prompt "\nChọn các nhãn cao độ đỉnh (TEXT trên layer SN-LUOI-NHAN): ")
  (if (setq ss (ssget '((0 . "TEXT") (-3 ("SANNEN")))))
    (setq ds (sn:nhan-dinh-ds (sn:ma-lo) ss)))
  ds)

(defun sn:cd-luu ()
  (setq *sn-cd-che* (get_tile "p_che") *sn-cd-gt* (get_tile "e_gt")
        *sn-cd-bm* (get_tile "p_bemat") *sn-cd-lydo* (get_tile "e_lydo")))

(defun sn:cd-khoi ( / n)
  (sn:vn-ds '(("t_ten" . "Hiệu chỉnh cao độ đỉnh lưới")
              ("t_tieu" . "Chọn các nhãn đỉnh, chọn cách hiệu chỉnh rồi Áp dụng")
              ("n_che" . "Cách hiệu chỉnh") ("n_gt" . "Giá trị (m)") ("n_bemat" . "Bề mặt") ("n_lydo" . "Lý do")
              ("b_chon" . "Chọn đỉnh trên bản vẽ…") ("b_ap_dung" . "Áp dụng") ("b_dong" . "Đóng")))
  (setq n (length *sn-cd-ds*))
  (sn:vn "t_chon" (strcat "Đã chọn " (itoa n) " nhãn đỉnh"))
  (start_list "p_che")
  (mapcar 'add_list '("Nâng / hạ tất cả đỉnh đã chọn một lượng (+/−)" "Đặt cao độ mới cho tất cả đỉnh đã chọn"))
  (end_list)
  (set_tile "p_che" *sn-cd-che*) (set_tile "e_gt" *sn-cd-gt*) (set_tile "e_lydo" *sn-cd-lydo*)
  (start_list "p_bemat") (mapcar 'add_list '("đo (cao độ thiết kế)" "mốc (cao độ tự nhiên)")) (end_list)
  (set_tile "p_bemat" *sn-cd-bm*)
  (sn:tt "Nâng/hạ: cộng thêm giá trị (âm = hạ) vào cao độ hiện có của từng nhãn đã chọn.")
  (action_tile "b_chon" "(sn:cd-luu) (done_dialog 2)")
  (action_tile "b_ap_dung" "(sn:cd-luu) (done_dialog 1)")
  (action_tile "b_dong" "(done_dialog 0)"))

(defun sn:l-capdo ( / ma gt bm)
  (if (sn:can-lot)
    (progn
      (setq *sn-cd-ds* nil ma 2)
      (while (= ma 2)
        (setq ma (sn:mo-dlg "sn_capdo" 'sn:cd-khoi))
        (if (= ma 2) (setq *sn-cd-ds* (sn:cd-chon))))
      (if (= ma 1)
        (progn
          (setq gt (sn:so *sn-cd-gt*) bm (if (= *sn-cd-bm* "0") "do" "moc"))
          (cond
            ((null gt) (sn:bao "Giá trị phải là số."))
            ((null *sn-cd-ds*) (sn:bao "Chưa chọn đỉnh nào."))
            (T
             (sn:cd-ap-dung *sn-cd-ds* bm
                            (if (= *sn-cd-che* "0") '(lambda (z) (+ z gt)) '(lambda (z) gt))
                            (if (/= (sn:cat *sn-cd-lydo*) "") *sn-cd-lydo* "Hiệu chỉnh cao độ đỉnh trong CAD")))))))))
(defun c:SN_CAPDO () (sn:chay-lenh "SN_CAPDO" 'sn:l-capdo))

(defun sn:l-nangcd ( / d ds bm)                          ; như DD_NANGCDTK của SNVN
  (if (sn:can-lot)
    (progn
      (setq d (getreal "\nGiá trị nâng cao độ thiết kế (âm = hạ) <0>: "))
      (if d
        (progn
          (initget "Do Moc")
          (setq bm (getkword "\nBề mặt [Do/Moc] <Do>: "))
          (setq bm (if (= bm "Moc") "moc" "do"))
          (if (setq ds (sn:cd-chon))
            (sn:cd-ap-dung ds bm '(lambda (z) (+ z d)) (strcat "Nâng cao độ " (sn:g d) " m trong CAD"))
            (sn:bao "Chưa chọn đỉnh nào.")))))))
(defun c:SN_NANGCD () (sn:chay-lenh "SN_NANGCD" 'sn:l-nangcd))

(defun sn:l-suadinh ( / e it z)                          ; sửa cao độ MỘT đỉnh (như nhấp đúp vào cao độ nút của SNVN)
  (if (sn:can-lot)
    (if (setq e (car (entsel "\nChọn nhãn cao độ đỉnh cần sửa: ")))
      (if (setq it (sn:nhan-dinh e))
        (if (member (cadr it) '("moc" "do"))
          (if (setq z (getreal (strcat "\nĐỉnh " (car it) " (" (cadr it) ") hiện " (sn:g (caddr it)) " m. Cao độ mới: ")))
            (sn:cd-ap-dung (list it) (cadr it) '(lambda (x) z) "Sửa cao độ đỉnh trong CAD"))
          (sn:bao "Đó là nhãn chênh cao (dz) — chọn nhãn cao độ mốc hoặc đo."))
        (sn:bao "Đối tượng đó không phải nhãn đỉnh của hệ thống.")))))
(defun c:SN_SUADINH () (sn:chay-lenh "SN_SUADINH" 'sn:l-suadinh))

;;; ===========================================================================================
;;; 14. ĐỒNG BỘ NHÃN TRONG BẢN VẼ → HỆ THỐNG (luoi --resync)
;;; ===========================================================================================
(defun sn:l-dongbo ( / ds csv kq vb)
  (if (sn:can-lot)
    (progn
      (setq ds (sn:nhan-dinh-ds (sn:ma-lo) nil))
      (if (null ds)
        (sn:bao "Bản vẽ chưa có nhãn đỉnh của lô này. Chạy SN_VE trước.")
        (progn
          (setq csv (strcat (sn:tmp) "\\sn_nhan.csv"))
          (sn:csv-nhan csv ds)
          (sn:bao (strcat "Đã xuất " (itoa (length ds)) " nhãn đỉnh. So với hệ thống…"))
          (setq kq (sn:chay "dong-bo" (strcat "--tu-file " (sn:q csv)) nil))
          (sn:in-chay kq)
          (setq vb (sn:get "ma_thoat" (sn:get "du_lieu" kq)))
          (if (and (sn:get "ok" kq) (= vb 1) (sn:xac-nhan "Nhận các chênh lệch trên vào hệ thống (grid_adjusted)? " nil))
            (progn
              (sn:in-chay (sn:chay "dong-bo" (strcat "--tu-file " (sn:q csv) " --chap-nhan") nil))
              (if (sn:xac-nhan "Tính lại khối lượng và vẽ lại? " T)
                (progn (sn:in-chay (sn:chay "chay" "--verb tinh" nil)) (sn:ve))))))))))
(defun c:SN_DONGBO () (sn:chay-lenh "SN_DONGBO" 'sn:l-dongbo))

;;; ===========================================================================================
;;; 15. MẶT CẮT ĐỊA HÌNH
;;; ===========================================================================================
(setq *sn-mc-a* nil *sn-mc-b* nil *sn-mc-goc* nil *sn-mc-ten* "MC1" *sn-mc-buoc* "1" *sn-mc-tl* "5")

(defun sn:mc-luu ()
  (setq *sn-mc-ten* (get_tile "e_ten") *sn-mc-buoc* (get_tile "e_buoc") *sn-mc-tl* (get_tile "e_tl")))

(defun sn:mc-khoi ()
  (sn:vn-ds '(("t_ten" . "Mặt cắt địa hình")
              ("n_ten" . "Tên mặt cắt") ("n_buoc" . "Bước lấy mẫu (m)") ("n_tl" . "Tỷ lệ đứng (phóng đại ×)")
              ("b_tuyen" . "Chọn tuyến cắt A – B…") ("b_diem" . "Chọn điểm đặt biểu đồ…")
              ("b_tao" . "Tạo mặt cắt") ("b_dong" . "Đóng")))
  (sn:vn-dong '("t_tieu" "t_tieu2") "Mặt cắt dọc tuyến A–B qua TIN mốc (xanh lá) và TIN đo (đỏ)." 62)
  (set_tile "e_ten" *sn-mc-ten*) (set_tile "e_buoc" *sn-mc-buoc*) (set_tile "e_tl" *sn-mc-tl*)
  (sn:vn-dong '("t_ab" "t_ab2")
              (if (and *sn-mc-a* *sn-mc-b*)
                (strcat "A (" (rtos (car *sn-mc-a*) 2 2) ", " (rtos (cadr *sn-mc-a*) 2 2) ")  B ("
                        (rtos (car *sn-mc-b*) 2 2) ", " (rtos (cadr *sn-mc-b*) 2 2) ")  L = "
                        (rtos (distance *sn-mc-a* *sn-mc-b*) 2 2) " m")
                "Chưa chọn tuyến cắt")
              60)
  (sn:vn-dong '("t_dd" "t_dd2" "t_dd3")
              (if *sn-mc-goc
                (strcat "Đặt biểu đồ tại (" (rtos (car *sn-mc-goc) 2 2) ", " (rtos (cadr *sn-mc-goc) 2 2) ")")
                (strcat "Chưa chọn — mặc định: ngay dưới TOÀN BỘ kết quả của lô (bảng, lưới, nhãn), cách tối thiểu 30 m, "
                        "canh trái theo hộp bao. Không đè lên bảng khối lượng."))
              62)
  (action_tile "b_tuyen" "(sn:mc-luu) (done_dialog 2)")
  (action_tile "b_diem"  "(sn:mc-luu) (done_dialog 3)")
  (action_tile "b_tao"   "(sn:mc-luu) (done_dialog 1)")
  (action_tile "b_dong"  "(done_dialog 0)"))

(defun sn:mc-chon-tuyen ( / a b)
  (if (setq a (sn:lay-diem "\nĐiểm đầu A của tuyến cắt: " nil))
    (if (setq b (sn:lay-diem "\nĐiểm cuối B: " a))
      (progn (setq *sn-mc-a* (list (car a) (cadr a)) *sn-mc-b* (list (car b) (cadr b)))
             (grdraw a b 6 1)))))

(defun sn:diem-ent (e / d tp r)                          ; các điểm (E N) đặc trưng của một đối tượng: TEXT/MTEXT/LINE/LWPOLYLINE
  (setq d (entget e) tp (cdr (assoc 0 d)))
  (foreach i d
    (if (or (= (car i) 10) (and (= tp "LINE") (= (car i) 11)))
      (setq r (cons (list (car (cdr i)) (cadr (cdr i))) r))))
  r)

(defun sn:hop-bao-lo (lo ten / ss i e xd pts xs ys)      ; hộp bao ((x1 y1) (x2 y2)) mọi đối tượng kết quả của lô, trừ mặt 3D và mặt cắt cùng tên
  (if (setq ss (ssget "X" '((-3 ("SANNEN")))))
    (repeat (setq i (sslength ss))
      (setq e (ssname ss (setq i (1- i))) xd (sn:xd-chuoi e))
      (if (and xd (>= (length xd) 4) (= (car xd) lo)
               (not (member (nth 3 xd) '("mat_3d" "qc")))
               (not (and (= (nth 3 xd) "mat_cat") (= (sn:xd-get xd "ten") ten))))
        (setq pts (append (sn:diem-ent e) pts)))))
  (if pts
    (progn
      (setq xs (mapcar 'car pts) ys (mapcar 'cadr pts))
      (list (list (apply 'min xs) (apply 'min ys)) (list (apply 'max xs) (apply 'max ys))))))

(defun sn:mc-tao ( / buoc tl goc kq d hb vung)
  (setq buoc (sn:so *sn-mc-buoc*) tl (sn:so *sn-mc-tl*))
  (cond
    ((not (and *sn-mc-a* *sn-mc-b*)) (sn:bao "Chưa chọn tuyến cắt A–B."))
    ((or (null buoc) (<= buoc 0)) (sn:bao "Bước lấy mẫu phải là số dương."))
    ((or (null tl) (<= tl 0)) (sn:bao "Tỷ lệ đứng phải là số dương."))
    (T
     ;; người đã chọn điểm đặt → dùng nguyên; chưa chọn → lõi đặt DƯỚI toàn bộ kết quả của lô (hộp bao đo ở đây) + đệm ≥ 30 m
     (setq goc *sn-mc-goc*)
     (if (null goc) (setq hb (sn:hop-bao-lo (sn:ma-lo) *sn-mc-ten*)))
     (setq kq (sn:chay-ve "mat-cat"
                (strcat "--a " (sn:en *sn-mc-a*) " --b " (sn:en *sn-mc-b*) " --buoc " (sn:g buoc)
                        " --ten=" (sn:q *sn-mc-ten*) " --ty-le-dung " (sn:g tl)
                        (cond (goc (strcat " --goc-ve " (sn:en goc)))
                              (hb (strcat " --trai-x=" (rtos (car (car hb)) 2 4) " --duoi-y=" (rtos (cadr (car hb)) 2 4)))
                              (T "")))))
     (if (sn:get "ok" kq)
       (progn
         (setq d (sn:get "du_lieu" kq))
         (if (and (sn:get "mac_dinh" d) (setq vung (sn:get "vung" d)) (= (length vung) 4))      ; đặt tự động → phóng tới biểu đồ cho người thấy
           (vl-catch-all-apply 'sn:zoom-w
             (list (list (- (nth 0 vung) 20.0) (- (nth 1 vung) 20.0))
                   (list (+ (nth 2 vung) 20.0) (+ (nth 3 vung) 20.0)))))
         (sn:bao (strcat "MẶT CẮT " *sn-mc-ten* ": dài " (rtos (sn:neu (sn:get "chieu_dai" d) 0.0) 2 2) " m · diện tích đào "
                         (rtos (sn:neu (sn:get "dien_tich_dao" d) 0.0) 2 3) " m² · đắp " (rtos (sn:neu (sn:get "dien_tich_dap" d) 0.0) 2 3)
                         " m²" (if (> (sn:neu (sn:get "doan_thieu" d) 0.0) 0) (strcat " · THIẾU DỮ LIỆU " (rtos (sn:get "doan_thieu" d) 2 1) " m") "")))
         (if (sn:get "csv" d) (sn:bao (strcat "Bảng cao độ: " (sn:get "csv" d)))))))))

(defun sn:l-matcat ( / ma)
  (if (sn:can-lot)
    (progn
      (setq ma 2)
      (while (member ma '(2 3))
        (setq ma (sn:mo-dlg "sn_matcat" 'sn:mc-khoi))
        (cond ((= ma 2) (sn:mc-chon-tuyen))
              ((= ma 3) (setq *sn-mc-goc* (sn:lay-diem "\nĐiểm đặt góc dưới-trái của biểu đồ mặt cắt: " nil)))))
      (if (= ma 1) (sn:mc-tao)))))
(defun c:SN_MATCAT () (sn:chay-lenh "SN_MATCAT" 'sn:l-matcat))

;;; ===========================================================================================
;;; 16. BẢNG BIỂU
;;; ===========================================================================================
(setq *sn-bang-loai* "0")                                 ; 0 = bảng tổng, 1 = tổng hợp, 2 = từng ô

(defun sn:bang-khoi ()
  (sn:vn-ds '(("t_ten" . "Bảng biểu khối lượng") ("t_tieu" . "Chọn loại bảng cần chèn vào bản vẽ (layer SN-BANG)")
              ("n_loai" . "Loại bảng")
              ("b_chen" . "Chèn vào bản vẽ") ("b_excel" . "Xuất Excel + hồ sơ")
              ("b_thumuc" . "Mở thư mục xuất") ("b_dong" . "Đóng")))
  (start_list "p_loai")
  (mapcar 'add_list '("Bảng tổng (số nộp: đào, đắp, diện tích)" "Bảng tổng hợp (nộp + kiểm + diện tích lô)" "Bảng từng ô"))
  (end_list)
  (set_tile "p_loai" *sn-bang-loai*)
  (sn:tt "Bảng lấy số từ volume.json — chạy SN_TINH trước nếu chưa có.")
  (action_tile "b_chen" "(setq *sn-bang-loai* (get_tile \"p_loai\")) (done_dialog 1)")
  (action_tile "b_excel" "(setq *sn-bang-loai* (get_tile \"p_loai\")) (done_dialog 2)")
  (action_tile "b_thumuc" "(setq *sn-bang-loai* (get_tile \"p_loai\")) (done_dialog 3)")
  (action_tile "b_dong" "(done_dialog 0)"))

(defun sn:l-bang ( / ma p loai)
  (if (sn:can-lot)
    (progn
      (setq ma (sn:mo-dlg "sn_bang" 'sn:bang-khoi))
      (cond
        ((= ma 1)
         (setq loai (cond ((= *sn-bang-loai* "1") "tong-hop") ((= *sn-bang-loai* "2") "o") (T "tong")))
         (if (setq p (sn:lay-diem "\nĐiểm chèn bảng (góc trên-trái): " nil))
           (sn:chay-ve "bang" (strcat "--loai " loai " --goc-ve " (sn:en p)))))
        ((= ma 2) (sn:l-verb "xuat"))
        ((= ma 3)
         (sn:thu '(lambda () (startapp "explorer.exe" (strcat "\"" (sn:cfg "lot") "\\20_output\"")))))))))
(defun c:SN_BANG () (sn:chay-lenh "SN_BANG" 'sn:l-bang))

;;; ===========================================================================================
;;; 17. CẢNH BÁO / QC
;;; ===========================================================================================
(setq *sn-cb-ds* nil *sn-cb-hien* nil *sn-cb-chan* "0" *sn-cb-diem* nil)

(defun sn:cb-muc-chu (m) (cond ((equal m "chan") "chặn") ((equal m "canh_bao") "cảnh báo") (T "thông tin")))

(defun sn:cb-loc ( / r)                                  ; danh sách hiện (đã lọc) theo ô "chỉ chặn"
  (setq r nil)
  (foreach i *sn-cb-ds*
    (if (or (/= *sn-cb-chan* "1") (equal (sn:get "muc" i) "chan")) (setq r (cons i r))))
  (reverse r))

(defun sn:cb-dien ( / dong)
  (setq *sn-cb-hien* (sn:cb-loc))
  (start_list "l_ds")
  (foreach i *sn-cb-hien*
    (setq dong (strcat (sn:neu (sn:get "ma" i) "?") " [" (sn:cb-muc-chu (sn:get "muc" i)) "] "
                       (let ((m (sn:cat-dong (sn:neu (sn:get "mo_ta" i) ""))))
                         (if (> (strlen m) 110) (strcat (substr m 1 107) "…") m))))
    (add_list dong))
  (end_list)
  (sn:vn "t_tieu" (strcat (itoa (length *sn-cb-hien*)) " việc hiển thị / " (itoa (length *sn-cb-ds*)) " tổng cộng")))

(defun sn:cb-lam-moi ( / kq)
  (setq kq (sn:chay "canh-bao" "" nil))
  (if (sn:get "ok" kq)
    (setq *sn-cb-ds* (sn:get "du_lieu" kq))
    (progn (setq *sn-cb-ds* nil) (sn:tt (strcat "Không đọc được cảnh báo: " (sn:neu (sn:get "thong_bao" kq) "?")))))
  (sn:cb-dien))

(defun sn:cb-doi-loc ()
  (setq *sn-cb-chan* (get_tile "t_chi_chan"))
  (sn:cb-dien))

(defun sn:cb-zoom ( / i it)                              ; "Zoom tới" đóng hộp thoại rồi mới zoom (lệnh không chạy được trong hộp thoại)
  (setq i (get_tile "l_ds"))
  (cond ((or (null i) (= i "")) (sn:tt "Chọn một dòng trong danh sách."))
        (T (setq it (nth (atoi i) *sn-cb-hien*))
           (if (and (sn:get "e" it) (sn:get "n" it))
             (progn (setq *sn-cb-diem* (list (sn:get "e" it) (sn:get "n" it))) (done_dialog 2))
             (sn:tt "Việc này không có toạ độ.")))))

(defun sn:cb-khoi ()
  (sn:vn-ds '(("t_ten" . "Cảnh báo và kiểm soát chất lượng") ("n_chi_chan" . "Chỉ hiện việc CHẶN")
              ("b_zoom" . "Zoom tới") ("b_lammoi" . "Làm mới") ("b_dong" . "Đóng")))
  (sn:vn "t_tt" "Chọn một dòng rồi bấm Zoom tới (nếu việc có toạ độ).")
  (set_tile "t_chi_chan" *sn-cb-chan*)
  (sn:cb-dien)
  (action_tile "t_chi_chan" "(sn:an 'sn:cb-doi-loc)")
  (action_tile "b_lammoi" "(sn:an 'sn:cb-lam-moi)")
  (action_tile "b_zoom" "(sn:an 'sn:cb-zoom)")
  (action_tile "b_dong" "(done_dialog 0)"))

(defun sn:zoom-c (p h) (command "_.ZOOM" "_C" p h))
(defun sn:zoom-w (p1 p2) (command "_.ZOOM" "_W" p1 p2))

(defun sn:zoom-toi (p / n i a b)                         ; zoom + vòng tròn tạm đánh dấu (grdraw — biến mất khi vẽ lại)
  (vl-catch-all-apply 'sn:zoom-c (list p 60.0))
  (setq n 36 i 0)
  (repeat n
    (setq a (polar p (* 2 pi (/ i n)) 3.0)
          b (polar p (* 2 pi (/ (1+ i) n)) 3.0))
    (grdraw a b 1 1)
    (setq i (1+ i))))

(defun sn:l-canhbao ( / ma kq)
  (if (sn:can-lot)
    (progn
      (setq kq (sn:chay "canh-bao" "" nil))
      (if (not (sn:get "ok" kq))
        (sn:bao (strcat "Không đọc được cảnh báo: " (sn:neu (sn:get "thong_bao" kq) "?")))
        (progn
          (setq *sn-cb-ds* (sn:get "du_lieu" kq) ma 2)
          (while (= ma 2)
            (setq ma (sn:mo-dlg "sn_canhbao" 'sn:cb-khoi))
            (if (and (= ma 2) *sn-cb-diem*) (sn:zoom-toi *sn-cb-diem*))))))))
(defun c:SN_CANHBAO () (sn:chay-lenh "SN_CANHBAO" 'sn:l-canhbao))

;;; ===========================================================================================
;;; 18. CỘNG Ô  (như DD_MC của SNVN)
;;; ===========================================================================================
(defun sn:lop (ten mau)                                   ; tạo layer nếu chưa có (PHẢI có trước khi entmake đối tượng)
  (if (not (tblsearch "LAYER" ten))
    (entmake (list '(0 . "LAYER") '(100 . "AcDbSymbolTableRecord") '(100 . "AcDbLayerTableRecord")
                   (cons 2 ten) '(70 . 0) (cons 62 mau)))))

(defun sn:mtext (p chu cao lop xd)                        ; MTEXT mang XDATA SANNEN (xd = danh sách chuỗi)
  (sn:lop lop 2)
  (entmake (list '(0 . "MTEXT") '(100 . "AcDbEntity") (cons 8 lop) '(100 . "AcDbMText")
                 (cons 10 (list (car p) (cadr p) 0.0)) (cons 40 cao) (cons 71 5) (cons 1 chu)
                 (list -3 (cons "SANNEN" (mapcar '(lambda (s) (cons 1000 s)) xd))))))

(defun sn:l-congo ( / p1 p2 o1 o2 dao dap lo mid)
  (if (sn:can-lot)
    (progn
      (setq lo (sn:ma-lo))
      (while (and (setq p1 (sn:lay-diem "\nChọn điểm trong ô thứ nhất <Enter để kết thúc>: " nil))
                  (setq p2 (sn:lay-diem "\nChọn điểm trong ô thứ hai: " nil)))
        (setq o1 (sn:o-tai p1) o2 (sn:o-tai p2))
        (cond
          ((not (and o1 o2)) nil)
          ((or (sn:get "thieu_du_lieu" o1) (sn:get "thieu_du_lieu" o2))
           (sn:bao "Một trong hai ô THIẾU DỮ LIỆU — không cộng (RULES 8)."))
          (T
           (setq dao (+ (sn:get "kl_dao" o1) (sn:get "kl_dao" o2)) dap (+ (sn:get "kl_dap" o1) (sn:get "kl_dap" o2))
                 mid (list (/ (+ (car p1) (car p2)) 2.0) (/ (+ (cadr p1) (cadr p2)) 2.0)))
           (sn:bao (strcat (sn:get "ma" o1) " + " (sn:get "ma" o2) ": đào " (rtos dao 2 2) " m³ · đắp " (rtos dap 2 2) " m³"))
           (sn:mtext mid (strcat (sn:get "ma" o1) " + " (sn:get "ma" o2) "\\PĐào " (rtos dao 2 1) "\\PĐắp " (rtos dap 2 1))
                     0.8 "SN-LUOI-O" (list lo (itoa (sn:dot)) "cong-o" "cong_o"))))))))
(defun c:SN_CONGO () (sn:chay-lenh "SN_CONGO" 'sn:l-congo))

;;; ===========================================================================================
;;; 19. DUYỆT CỔNG (người quyết; agent không tự duyệt)
;;; ===========================================================================================
(setq *sn-dy-cong* "0" *sn-dy-nguoi* "" *sn-dy-bc* "" *sn-dy-tt* nil)         ; cong: 0 = cổng 1, 1 = cổng 2, 2 = cổng 3

(defun sn:dy-cong-ds (cong n / c)                         ; trạng thái cổng n trong alist `cong` (khoá có thể là "1" hoặc 1)
  (setq c (sn:neu (assoc (itoa n) cong) (assoc n cong)))
  (if c (cdr c)))

(defun sn:dy-dien ( / n c ds)
  (setq n 0)
  (foreach k '("t_c1" "t_c2" "t_c3")
    (setq n (1+ n))
    (setq ds (sn:dy-cong-ds *sn-dy-tt* n))
    (sn:vn k (strcat "Cổng " (itoa n) ": "
                     (cond ((null ds) "chưa rõ")
                           ((sn:get "da_duyet" ds) "ĐÃ DUYỆT")
                           (T (strcat "chưa duyệt" (if (> (fix (sn:neu (sn:get "viec_chan" ds) 0)) 0)
                                                    (strcat " — còn " (itoa (fix (sn:get "viec_chan" ds))) " việc CHẶN") ""))))))))

(defun sn:dy-lam-moi ( / kq)
  (setq kq (sn:chay "trang-thai" "" nil))
  (setq *sn-dy-tt* (if (sn:get "ok" kq) (sn:get "cong" (sn:get "du_lieu" kq)) nil))
  (sn:dy-dien))

(defun sn:cb-duyet ( / n ng bc kq)                        ; callback nút Duyệt
  (setq n (1+ (atoi (get_tile "p_cong")))
        ng (sn:cat (get_tile "e_nguoi")) bc (sn:cat (get_tile "e_bc")))
  (cond
    ((= ng "") (sn:tt "Phải ghi tên người duyệt."))
    ((= bc "") (sn:tt "Phải ghi NGUYÊN VĂN câu đồng ý của người duyệt — không được để trống."))
    (T
     (setq kq (sn:chay "duyet" (strcat "--cong " (itoa n) " --nguoi=" (sn:q ng) " --bang-chung=" (sn:q bc)) nil))
     (if (sn:get "ok" kq)
       (progn (sn:tt (strcat "Đã ghi duyệt cổng " (itoa n) ".")) (sn:dy-lam-moi))
       (sn:tt (strcat "Không duyệt được: " (sn:neu (sn:get "thong_bao" kq) "?")))))))

(defun sn:dy-khoi ()
  (sn:vn-ds '(("t_ten" . "Duyệt cổng")
              ("n_cong" . "Cổng cần duyệt") ("n_nguoi" . "Người duyệt") ("n_bc" . "Câu đồng ý (nguyên văn)")
              ("b_duyet" . "Duyệt cổng") ("b_dong" . "Đóng")))
  (sn:vn-dong '("t_tieu" "t_tieu2") "Duyệt cổng do NGƯỜI quyết định. Agent không tự duyệt thay người." 62)
  (start_list "p_cong")
  (mapcar 'add_list '("Cổng 1 — dữ liệu (sau nhập)" "Cổng 2 — bề mặt (sau mặt + lô)" "Cổng 3 — số liệu (sau tính)"))
  (end_list)
  (set_tile "p_cong" *sn-dy-cong*)
  (sn:dy-lam-moi)
  (sn:tt "Ghi rõ người duyệt và nguyên văn câu đồng ý (được lưu vào 90_log/decisions.md).")
  (action_tile "b_duyet" "(sn:an 'sn:cb-duyet)")
  (action_tile "b_dong" "(setq *sn-dy-cong* (get_tile \"p_cong\")) (done_dialog 0)"))

(defun sn:l-duyet ()
  (if (sn:can-lot) (sn:mo-dlg "sn_duyet" 'sn:dy-khoi)))
(defun c:SN_DUYET () (sn:chay-lenh "SN_DUYET" 'sn:l-duyet))

;;; ===========================================================================================
;;; 19B. BẢNG ĐIỀU KHIỂN TRUNG TÂM  (SN_QL)
;;; ===========================================================================================
;;; MỘT hộp thoại gom: thông tin lô + ba cổng + cảnh báo "kết quả cũ" (đầu hộp); danh sách NHÓM ĐỐI TƯỢNG với số đối
;;; tượng đếm trong bản vẽ (đúng lô, đúng đợt: XDATA SANNEN) và trạng thái Hiện/Ẩn đọc từ bản vẽ mỗi lần mở; khung số liệu
;;; chi tiết theo nhóm (cầu nối `thong-tin` — lõi chỉ ĐỌC file, không tính); các nút nhảy sang thao tác điều chỉnh.
;;; Ẩn/hiện CHỈ bằng ON/OFF layer (sn:lop-bat) — không đóng băng, không xóa, không đổi layer hiện hành, không đụng layer
;;; ngoài "SN-*". Hộp KHÔNG tự tính (RULES 1) và mọi lệnh ghi vẫn xin xác nhận như khi gọi trực tiếp (RULES 4).
;;;
;;; Bảng nhóm: (khoá  tên-có-dấu  kiểu-layer  gốc-layer  có-XDATA?)
;;;   kiểu "dot"    = layer của nhóm là gốc (đợt 1) hoặc gốc-Dnn (đợt n) — đúng backend.ten_layer
;;;   kiểu "co-dinh"= layer luôn đúng tên gốc (SN-MATCAT, SN-BANG)
;;;   kiểu "mau"    = mẫu wcmatch nhiều layer nguồn của nhà thầu (đếm theo layer, không có XDATA)
(setq *sn-ql-nhom*
  '(("moc"       "TIN mốc"                  "dot"     "SN-3DF-MOC"      T)
    ("do"        "TIN đo"                   "dot"     "SN-3DF-DO"       T)
    ("qc"        "Tam giác thiếu dữ liệu"   "dot"     "SN-QC"           T)
    ("luoi"      "Lưới ô"                   "dot"     "SN-LUOI"         T)
    ("nhan"      "Nhãn đỉnh lưới"           "dot"     "SN-LUOI-NHAN"    T)
    ("o"         "Nhãn ô (khối lượng)"      "dot"     "SN-LUOI-O"       T)
    ("ranh"      "Ranh đào–đắp"             "dot"     "SN-RANH-DAODAP"  T)
    ("matcat"    "Mặt cắt"                  "co-dinh" "SN-MATCAT"       T)
    ("bang"      "Bảng in"                  "co-dinh" "SN-BANG"         T)
    ("khoiluong" "Khối lượng (số liệu)"     nil       nil               nil)
    ("nguon"     "Dữ liệu nguồn (nhà thầu)" "mau"
     "SN-DIEM-MOC*,SN-DIEM-DO*,SN-DUTGAY*,SN-DONGMUC*,SN-BIENLO*,SN-LOAITRU*" nil)))

;; nhóm của ql → nhóm của `ve` (cad/sannen_cad/ve.py: luoi, nhan, o, ranh, 3d, bang). Mặt cắt chỉ vẽ lại bằng SN_MATCAT.
(setq *sn-ql-ve* '(("moc" . "3d") ("do" . "3d") ("qc" . "3d") ("luoi" . "luoi") ("nhan" . "nhan") ("o" . "o")
                   ("ranh" . "ranh") ("bang" . "bang")))
;; nút → lệnh có sẵn (đóng hộp, chạy lệnh, mở lại hộp để cập nhật)
(setq *sn-ql-lenh* '((1 . "SN_TIN3D") (2 . "SN_XEM3D") (3 . "SN_LUOI") (4 . "SN_MATCAT") (5 . "SN_CAPDO")
                     (6 . "SN_CANHBAO") (7 . "SN_BANG") (8 . "SN_TINH") (10 . "SN_DUYET")))

(setq *sn-ql-chon* "0"     ; dòng đang chọn trong danh sách nhóm (chuỗi get_tile) — nhớ giữa các lần mở lại
      *sn-ql-tt* nil       ; du_lieu của cầu nối thong-tin (nil = chưa đọc được)
      *sn-ql-loi* nil      ; lý do không đọc được
      *sn-ql-dem* nil      ; alist (khoá . số đối tượng) đếm trong bản vẽ; nil = nhóm chưa có layer
      *sn-ql-lo* nil *sn-ql-dot* nil
      *sn-ql-can-regen* nil *sn-ql-bo-qua* nil)

(defun sn:ql-join (ds sep / r)
  (setq r "")
  (foreach s ds (setq r (if (= r "") s (strcat r sep s))))
  r)

(defun sn:ql-ten-dot (goc dot)                            ; như backend.ten_layer: đợt 1 → gốc; đợt n → gốc-Dnn
  (if (and dot (> dot 1)) (strcat goc "-D" (if (< dot 10) "0" "") (itoa dot)) goc))

(defun sn:ql-mau-lop (g / kieu goc)                       ; mẫu wcmatch (HOA) các layer của nhóm; nil nếu nhóm không có layer
  (setq kieu (nth 2 g) goc (nth 3 g))
  (cond ((null goc) nil)
        ((= kieu "dot") (sn:ql-ten-dot goc (sn:neu *sn-ql-dot* 1)))
        (T goc)))

(defun sn:ql-lop-cua (g / pat d r n)                      ; tên layer THỰC CÓ trong bản vẽ của nhóm
  (if (setq pat (sn:ql-mau-lop g))
    (progn
      (setq d (tblnext "LAYER" T))
      (while d
        (setq n (cdr (assoc 2 d)))
        (if (and (wcmatch (strcase n) (strcase pat)) (not (vl-string-search "|" n))) (setq r (cons n r)))
        (setq d (tblnext "LAYER")))))
  (reverse r))

(defun sn:ql-lop-sn ( / d r n)                            ; MỌI layer SN-* (mọi đợt, mọi nhóm) — cho nút "tất cả SAN NỀN"
  (setq d (tblnext "LAYER" T))
  (while d
    (setq n (cdr (assoc 2 d)))
    (if (and (wcmatch (strcase n) "SN-*") (not (vl-string-search "|" n))) (setq r (cons n r)))
    (setq d (tblnext "LAYER")))
  (reverse r))

(defun sn:ql-lop-tt (ten / r)                             ; "hien" | "an" (OFF) | "dong-bang"
  (setq r (tblsearch "LAYER" ten))
  (cond ((null r) nil)
        ((/= 0 (logand 1 (cdr (assoc 70 r)))) "dong-bang")
        ((< (cdr (assoc 62 r)) 0) "an")
        (T "hien")))

(defun sn:ql-trang-thai (g / ds ts)                       ; "hien" | "an" | "mot-phan" | "dong-bang" | "khong" (chưa có layer / không áp dụng)
  (setq ds (sn:ql-lop-cua g))
  (cond ((null ds) "khong")
        (T (setq ts (mapcar 'sn:ql-lop-tt ds))
           (cond ((member "dong-bang" ts) "dong-bang")
                 ((null (vl-remove-if '(lambda (x) (= x "hien")) ts)) "hien")
                 ((null (vl-remove-if '(lambda (x) (= x "an")) ts)) "an")
                 (T "mot-phan")))))

(defun sn:ql-chu-tt (g / st)
  (setq st (sn:ql-trang-thai g))
  (cond ((null (nth 3 g)) "—")
        ((= st "hien") "Hiện") ((= st "an") "Ẩn") ((= st "mot-phan") "Một phần")
        ((= st "dong-bang") "Đóng băng") (T "Chưa có lớp")))

(defun sn:ql-ss-nhom (g lo dot / ds ss i e xd r)          ; tập chọn các đối tượng CỦA ĐÚNG lô+đợt trong nhóm (nil nếu không có)
  ;; nhóm có XDATA: lọc theo XDATA SANNEN (mã lô, đợt); nhóm nguồn: mọi đối tượng trên layer.
  (if (setq ds (sn:ql-lop-cua g))
    (progn
      (setq ss (ssget "X" (append (list (cons 8 (sn:ql-join ds ","))) (if (nth 4 g) '((-3 ("SANNEN"))))))
            r (ssadd))
      (if ss
        (repeat (setq i (sslength ss))
          (setq e (ssname ss (setq i (1- i))))
          (if (nth 4 g)
            (progn (setq xd (sn:xd-chuoi e))
                   (if (and xd (>= (length xd) 4) (= (car xd) lo) (= (cadr xd) (itoa dot))) (ssadd e r)))
            (ssadd e r))))))
  (if (and r (> (sslength r) 0)) r))

(defun sn:ql-dem-nhom (g lo dot / ss)                     ; số đối tượng; nil nếu nhóm chưa có layer trong bản vẽ
  (cond ((null (sn:ql-lop-cua g)) nil)
        ((setq ss (sn:ql-ss-nhom g lo dot)) (sslength ss))
        (T 0)))

(defun sn:ql-nap ( / kq)                                  ; đọc thông tin từ lõi + đếm đối tượng trong bản vẽ (mỗi lần mở/làm mới)
  (setq kq (sn:chay "thong-tin" "" nil))
  (if (sn:get "ok" kq)
    (setq *sn-ql-tt* (sn:get "du_lieu" kq) *sn-ql-loi* nil)
    (setq *sn-ql-tt* nil *sn-ql-loi* (sn:neu (sn:get "thong_bao" kq) "lỗi không rõ")))
  (setq *sn-ql-lo* (sn:neu (sn:ma-lo) "") *sn-ql-dot* (sn:dot) *sn-ql-dem* nil)
  (foreach g *sn-ql-nhom*
    (setq *sn-ql-dem* (cons (cons (car g) (sn:ql-dem-nhom g *sn-ql-lo* *sn-ql-dot*)) *sn-ql-dem*)))
  *sn-ql-tt*)

(defun sn:ql-parse-chon (s / r)                           ; "0 3 5" → (0 3 5)
  (foreach p (sn:chia (sn:neu s "") " ") (if (/= p "") (setq r (cons (atoi p) r))))
  (reverse r))

(defun sn:ql-nhom-chon (s / r)                            ; chuỗi chọn → danh sách các nhóm
  (foreach i (sn:ql-parse-chon s) (if (nth i *sn-ql-nhom*) (setq r (cons (nth i *sn-ql-nhom*) r))))
  (reverse r))

(defun sn:ql-bat-ds (ds bat / n cl)                       ; ON/OFF các layer trong ds (KHÔNG tắt layer hiện hành); trả số layer đổi
  (setq n 0 cl (strcase (getvar "CLAYER")))
  (foreach l ds
    (cond ((and (not bat) (= (strcase l) cl)) (setq *sn-ql-bo-qua* (cons l *sn-ql-bo-qua*)))
          ((sn:lop-bat l bat) (setq n (1+ n)))))
  n)

(defun sn:ql-bat-nhom (g bat)
  (sn:ql-bat-ds (sn:ql-lop-cua g) bat))

(defun sn:ql-chi-hien (gs / giu r n)                      ; BẬT layer của các nhóm gs, TẮT mọi layer SN-* còn lại
  (setq giu nil n 0)
  (foreach g gs (setq giu (append giu (mapcar 'strcase (sn:ql-lop-cua g)))))
  (foreach l (sn:ql-lop-sn)
    (setq n (+ n (sn:ql-bat-ds (list l) (if (member (strcase l) giu) T nil)))))
  n)

;;; ---- văn bản hiển thị -------------------------------------------------------------------------
(setq *sn-ql-buoc* '(("nhap" . "nhập") ("mat" . "mặt TIN") ("lo" . "biên lô") ("luoi" . "lưới") ("tinh" . "tính") ("xuat" . "xuất")))

(defun sn:ql-buoc-chu (tt / b ke)
  (setq b (sn:get "buoc" tt) ke (sn:get "buoc_ke_tiep" tt))
  (strcat "Đã chạy:  "
          (apply 'strcat (mapcar '(lambda (p) (strcat (if (sn:get (car p) b) "[x] " "[ ] ") (cdr p) "    ")) *sn-ql-buoc*))
          (if ke (strcat "→ kế tiếp: " (sn:neu (sn:get ke *sn-ql-buoc*) ke)) "→ đã đủ các bước")))

(defun sn:ql-cong-chu (tt / cg r ds)
  (setq cg (sn:get "cong" tt) r "")
  (foreach n '(1 2 3)
    (setq ds (sn:dy-cong-ds cg n))
    (setq r (strcat r (if (> n 1) "    |    " "") "Cổng " (itoa n) ": "
                    (cond ((null ds) "chưa rõ")
                          ((sn:get "da_duyet" ds) "ĐÃ duyệt")
                          (T (strcat "chưa duyệt"
                                     (if (> (fix (sn:neu (sn:get "viec_chan" ds) 0)) 0)
                                       (strcat " (còn " (itoa (fix (sn:get "viec_chan" ds))) " việc CHẶN)") "")))))))
  r)

(defun sn:ql-cu-chu (tt / ds)                             ; cảnh báo "kết quả cũ" (đã nhóm thành một đoạn)
  (setq ds (sn:get "canh_bao_cu" tt))
  (if ds
    (strcat "CẢNH BÁO KẾT QUẢ CŨ: " (sn:ql-join ds "  •  "))
    "Kết quả khớp lưới và bề mặt hiện tại (không phát hiện kết quả cũ)."))

(defun sn:ql-dong-nhom (g / n)                            ; một hàng của danh sách nhóm: tên ⇥ số đối tượng ⇥ trạng thái
  (setq n (cdr (assoc (car g) *sn-ql-dem*)))
  (strcat (cadr g) "\t"
          (cond ((null (nth 3 g)) "—") ((null n) "(chưa có lớp)") (T (strcat (itoa n) " đối tượng")))
          "\t" (sn:ql-chu-tt g)))

(defun sn:ql-ct-dong (g / k n r ds sl)                    ; các dòng "nhãn ⇥ giá trị" của khung số liệu theo nhóm
  (setq k (car g) n (cdr (assoc k *sn-ql-dem*)) r nil)
  (if (nth 3 g)
    (progn
      (setq ds (sn:ql-lop-cua g))
      (setq r (list (strcat "Lớp (layer)\t" (if ds (sn:ql-join ds ", ") (strcat "chưa có trong bản vẽ: " (sn:ql-mau-lop g))))
                    (strcat "Đối tượng trong bản vẽ\t" (if n (itoa n) "—")
                            (if (nth 4 g) (strcat " (lô " *sn-ql-lo* ", đợt " (itoa (sn:neu *sn-ql-dot* 1)) ")") " (mọi đối tượng trên lớp)"))
                    (strcat "Hiển thị\t" (sn:ql-chu-tt g))))))
  (if *sn-ql-tt*
    (foreach p (sn:get k (sn:get "nhom" *sn-ql-tt*))
      (setq r (append r (list (strcat (sn:vs (car p)) "\t" (sn:vs (cadr p)))))))
    (setq r (append r (list (strcat "Số liệu\tChưa có — " (sn:neu *sn-ql-loi* "chưa đọc từ lõi"))))))
  r)

;;; ---- hộp thoại ------------------------------------------------------------------------------------
(defun sn:ql-dien-dau ( / tt)
  (setq tt *sn-ql-tt*)
  (cond
    (tt
     (sn:vn "t_lo" (strcat "Lô " (sn:neu (sn:get "ma_lo" (sn:get "lo" tt)) "?") "   ·   đợt " (sn:vs (sn:get "dot" (sn:get "lo" tt)))
                           "   ·   thư mục " (sn:neu (sn:get "thu_muc" (sn:get "lo" tt)) "?")))
     (sn:vn "t_buoc" (sn:ql-buoc-chu tt))
     (sn:vn "t_cong" (sn:ql-cong-chu tt))
     (sn:vn-dong '("t_cu" "t_cu2") (sn:ql-cu-chu tt) 118))
    (T
     (sn:vn "t_lo" (strcat "Lô " (sn:neu (sn:ma-lo) "?") " — chưa đọc được số liệu từ lõi"))
     (sn:vn "t_buoc" "Đã chạy:  chưa rõ")
     (sn:vn "t_cong" "Cổng 1: chưa rõ    |    Cổng 2: chưa rõ    |    Cổng 3: chưa rõ")
     (sn:vn-dong '("t_cu" "t_cu2")
                 (strcat "Không đọc được thông tin lô: " (sn:neu *sn-ql-loi* "?") " — kiểm tra cấu hình " (sn:cfg-file)
                         " (python=, cad=, lot=) rồi bấm Làm mới. Phần Hiện/Ẩn nhóm vẫn dùng được.") 118))))

(defun sn:ql-dien-ds ()                                   ; đổ danh sách nhóm (trạng thái đọc LẠI từ bản vẽ) và đặt lại dòng chọn
  (start_list "l_nhom")
  (foreach g *sn-ql-nhom* (add_list (sn:ql-dong-nhom g)))
  (end_list)
  (set_tile "l_nhom" (sn:neu *sn-ql-chon* "0")))

(defun sn:ql-dien-ct ( / gs g)                            ; khung số liệu theo nhóm đang chọn (dòng đầu tiên nếu chọn nhiều)
  (setq gs (sn:ql-nhom-chon (get_tile "l_nhom")))
  (start_list "l_ct")
  (cond
    ((null gs) (add_list "Chọn một nhóm ở bên trái để xem số liệu."))
    (T (setq g (car gs))
       (foreach d (sn:ql-ct-dong g) (add_list d))))
  (end_list)
  (sn:vn "t_cttieu" (if gs (strcat "Số liệu: " (cadr (car gs)) (if (> (length gs) 1) (strcat "   (+" (itoa (1- (length gs))) " nhóm khác đang chọn)") ""))
                      "Số liệu chi tiết")))

(defun sn:ql-luu ()
  (setq *sn-ql-chon* (get_tile "l_nhom")))

(defun sn:ql-cb-chon ()
  (sn:ql-luu)
  (sn:ql-dien-ct))

(defun sn:ql-lam-lai-hien-thi ()                          ; cập nhật danh sách + chi tiết sau khi đổi Hiện/Ẩn
  (sn:ql-luu)
  (sn:ql-dien-ds)
  (sn:ql-dien-ct))

(defun sn:ql-tom-tat-bat (n bat)
  (strcat (if bat "Đã BẬT " "Đã TẮT ") (itoa n) " layer (chỉ ON/OFF — không đóng băng, không xóa)."
          (if *sn-ql-bo-qua* (strcat " Giữ nguyên layer hiện hành: " (sn:ql-join *sn-ql-bo-qua* ", ") " (không tắt được layer đang vẽ).") "")))

(defun sn:ql-cb-bat (bat / gs n)                          ; nút Hiện / Ẩn cho các nhóm đang chọn
  (sn:ql-luu)
  (setq gs (sn:ql-nhom-chon *sn-ql-chon*) n 0 *sn-ql-bo-qua* nil)
  (cond ((null gs) (sn:tt "Chọn ít nhất một nhóm trong danh sách."))
        ((null (vl-remove-if-not '(lambda (g) (nth 3 g)) gs)) (sn:tt "Nhóm này không có đối tượng vẽ để hiện/ẩn."))
        (T (foreach g gs (setq n (+ n (sn:ql-bat-nhom g bat))))
           (setq *sn-ql-can-regen* T)
           (sn:ql-lam-lai-hien-thi)
           (sn:tt (sn:ql-tom-tat-bat n bat)))))

(defun sn:ql-cb-chi ( / gs n)                             ; "Chỉ hiện nhóm này": các nhóm chọn BẬT, mọi layer SN-* khác TẮT
  (sn:ql-luu)
  (setq gs (vl-remove-if-not '(lambda (g) (nth 3 g)) (sn:ql-nhom-chon *sn-ql-chon*)) *sn-ql-bo-qua* nil)
  (cond ((null gs) (sn:tt "Chọn ít nhất một nhóm có đối tượng vẽ."))
        (T (setq n (sn:ql-chi-hien gs))
           (setq *sn-ql-can-regen* T)
           (sn:ql-lam-lai-hien-thi)
           (sn:tt (strcat "Chỉ hiện: " (sn:ql-join (mapcar 'cadr gs) ", ") ". " (sn:ql-tom-tat-bat n nil)
                          " Layer ngoài SAN NỀN không bị đụng tới.")))))

(defun sn:ql-cb-tat-ca (bat / n)                          ; "Hiện / Ẩn tất cả SAN NỀN": mọi layer SN-*
  (sn:ql-luu)
  (setq *sn-ql-bo-qua* nil n (sn:ql-bat-ds (sn:ql-lop-sn) bat))
  (setq *sn-ql-can-regen* T)
  (sn:ql-lam-lai-hien-thi)
  (sn:tt (strcat (if bat "Hiện tất cả layer SN-*. " "Ẩn tất cả layer SN-*. ") (sn:ql-tom-tat-bat n bat))))

(defun sn:ql-cb-lam-moi ()
  (sn:ql-luu)
  (sn:tt "Đang đọc lại thông tin từ lõi và bản vẽ…")
  (sn:ql-nap)
  (sn:ql-dien-dau)
  (sn:ql-dien-ds)
  (sn:ql-dien-ct)
  (sn:tt (if *sn-ql-tt* "Đã làm mới số liệu và trạng thái hiển thị." (strcat "Chưa đọc được số liệu: " (sn:neu *sn-ql-loi* "?")))))

(defun sn:ql-cb-zoom ( / gs)                              ; "Zoom tới nhóm": đóng hộp rồi mới zoom (lệnh không chạy được trong hộp thoại)
  (sn:ql-luu)
  (setq gs (sn:ql-nhom-chon *sn-ql-chon*))
  (cond ((null gs) (sn:tt "Chọn ít nhất một nhóm."))
        ((null (vl-remove-if-not
                 '(lambda (g) (and (nth 3 g) (> (sn:neu (cdr (assoc (car g) *sn-ql-dem*)) 0) 0)
                                   (member (sn:ql-trang-thai g) '("hien" "mot-phan"))))
                 gs))
         (sn:tt "Nhóm chọn chưa có đối tượng nào đang HIỆN — bấm Hiện hoặc vẽ nhóm đó trước."))
        (T (done_dialog 11))))

(defun sn:ql-cb-ve ( / gs)                                ; "Vẽ lại các nhóm đang chọn": kiểm tra rồi đóng hộp (vẽ cần xác nhận ở dòng lệnh)
  (sn:ql-luu)
  (setq gs (sn:ql-nhom-chon *sn-ql-chon*))
  (cond ((null gs) (sn:tt "Chọn ít nhất một nhóm."))
        ((null (sn:ql-ve-nhom gs))
         (sn:tt "Các nhóm chọn không vẽ lại từ đây: mặt cắt dùng SN_MATCAT; khối lượng và dữ liệu nguồn không có đối tượng vẽ."))
        (T (done_dialog 9))))

(defun sn:ql-ve-nhom (gs / r v)                           ; các nhóm của `ve` tương ứng (không trùng, giữ thứ tự)
  (foreach g gs
    (if (and (setq v (cdr (assoc (car g) *sn-ql-ve*))) (not (member v r))) (setq r (append r (list v)))))
  r)

(defun sn:ql-khoi ( / n)
  (sn:vn-ds '(("t_ten" . "SAN NỀN — Bảng điều khiển trung tâm: TIN, lưới ô vuông, khối lượng, hiển thị")
              ("t_cot" . "Nhóm đối tượng (giữ Ctrl / Shift để chọn nhiều nhóm)")
              ("b_hien" . "Hiện") ("b_an" . "Ẩn") ("b_chi" . "Chỉ hiện nhóm này")
              ("b_hien_het" . "Hiện tất cả SAN NỀN") ("b_an_het" . "Ẩn tất cả SAN NỀN") ("b_zoom" . "Zoom tới nhóm")
              ("b_tin3d" . "Xem 3D…") ("b_xem3d" . "Trình xem HTML") ("b_luoi" . "Hiệu chỉnh lưới…")
              ("b_matcat" . "Mặt cắt…") ("b_capdo" . "Cao độ đỉnh…") ("b_canhbao" . "Cảnh báo QC…")
              ("b_bang" . "Bảng biểu…") ("b_tinh" . "Tính lại") ("b_ve" . "Vẽ lại nhóm đang chọn")
              ("b_duyet" . "Duyệt cổng…") ("b_lammoi" . "Làm mới") ("b_dong" . "Đóng")))
  (sn:ql-dien-dau)
  (sn:ql-dien-ds)
  (sn:ql-dien-ct)
  (setq n (length (sn:doc-lop-an)))
  (sn:tt (if (> n 0)
           (strcat "Đang ẩn " (itoa n) " layer ngoài SAN NỀN để xem riêng mặt 3D — khôi phục bằng SN_TIN3D → Khôi phục lớp. "
                   "Hộp này chỉ bật/tắt layer SN-*.")
           "Hiện/Ẩn chỉ bật-tắt layer SN-* (không đóng băng, không xóa). Hộp chỉ điều phối; mọi phép tính do lõi, lệnh ghi vẫn xin xác nhận."))
  (action_tile "l_nhom" "(sn:an 'sn:ql-cb-chon)")
  (action_tile "b_hien" "(sn:an '(lambda () (sn:ql-cb-bat T)))")
  (action_tile "b_an" "(sn:an '(lambda () (sn:ql-cb-bat nil)))")
  (action_tile "b_chi" "(sn:an 'sn:ql-cb-chi)")
  (action_tile "b_hien_het" "(sn:an '(lambda () (sn:ql-cb-tat-ca T)))")
  (action_tile "b_an_het" "(sn:an '(lambda () (sn:ql-cb-tat-ca nil)))")
  (action_tile "b_zoom" "(sn:an 'sn:ql-cb-zoom)")
  (action_tile "b_tin3d" "(sn:ql-luu) (done_dialog 1)")
  (action_tile "b_xem3d" "(sn:ql-luu) (done_dialog 2)")
  (action_tile "b_luoi" "(sn:ql-luu) (done_dialog 3)")
  (action_tile "b_matcat" "(sn:ql-luu) (done_dialog 4)")
  (action_tile "b_capdo" "(sn:ql-luu) (done_dialog 5)")
  (action_tile "b_canhbao" "(sn:ql-luu) (done_dialog 6)")
  (action_tile "b_bang" "(sn:ql-luu) (done_dialog 7)")
  (action_tile "b_tinh" "(sn:ql-luu) (done_dialog 8)")
  (action_tile "b_ve" "(sn:an 'sn:ql-cb-ve)")
  (action_tile "b_duyet" "(sn:ql-luu) (done_dialog 10)")
  (action_tile "b_lammoi" "(sn:an 'sn:ql-cb-lam-moi)")
  (action_tile "b_dong" "(sn:ql-luu) (done_dialog 0)"))

;;; ---- việc làm SAU khi hộp đóng (lệnh `command` không chạy được trong hộp thoại) ----------------------
(defun sn:ql-zoom ( / tong ss n i)
  (setq tong (ssadd) n 0)
  (foreach g (sn:ql-nhom-chon *sn-ql-chon*)
    (if (and (nth 3 g) (member (sn:ql-trang-thai g) '("hien" "mot-phan")) (setq ss (sn:ql-ss-nhom g *sn-ql-lo* *sn-ql-dot*)))
      (repeat (setq i (sslength ss))
        (ssadd (ssname ss (setq i (1- i))) tong)
        (setq n (1+ n)))))
  (if (> (sslength tong) 0)
    (progn (sn:thu (list 'lambda nil (list 'command "_.ZOOM" "_O" tong "")))
           (sn:bao (strcat "Đã zoom tới " (itoa (sslength tong)) " đối tượng của nhóm đang chọn.")))
    (sn:bao "Không có đối tượng đang hiện để zoom tới.")))

(defun sn:ql-ve-lai ( / ds)
  (setq ds (sn:ql-ve-nhom (sn:ql-nhom-chon *sn-ql-chon*)))
  (cond
    ((null ds) (sn:bao "Nhóm đang chọn không vẽ lại từ đây (mặt cắt: SN_MATCAT)."))
    ((sn:xac-nhan (strcat "Vẽ lại nhóm [" (sn:ql-join ds ", ") "] của lô " *sn-ql-lo*
                          " (xóa kết quả cũ cùng nhóm của ĐÚNG lô này rồi vẽ mới từ số liệu hiện có)? ") nil)
     (sn:chay-ve "ve" (strcat "--lop " (sn:ql-join ds ",")))
     (if (member "3d" ds) (sn:bao "Mặt 3D vẽ xong mặc định TẮT (layer-convention): bật lại ở SN_QL (Hiện) hoặc SN_TIN3D.")))
    (T (sn:bao "Đã hủy — không vẽ lại."))))

(defun sn:ql-chay-nut (ma / ten)                          ; nút → lệnh có sẵn; lệnh tự bọc lỗi và tự xin xác nhận nếu ghi
  (cond
    ((setq ten (cdr (assoc ma *sn-ql-lenh*)))
     (vl-catch-all-apply (read (strcat "c:" ten)) nil))
    ((= ma 9) (sn:ql-ve-lai))
    ((= ma 11) (sn:ql-zoom))))

(defun sn:l-ql ( / ma)
  (if (sn:can-lot)
    (progn
      (setq ma -1)
      (while (and ma (/= ma 0))
        (sn:ql-nap)
        (setq *sn-ql-can-regen* nil)
        (setq ma (sn:mo-dlg "sn_ql" 'sn:ql-khoi))
        (if *sn-ql-can-regen* (sn:thu '(lambda () (command "_.REGEN"))))
        (if (and ma (> ma 0)) (sn:ql-chay-nut ma))))))
(defun c:SN_QL () (sn:chay-lenh "SN_QL" 'sn:l-ql))

;;; ===========================================================================================
;;; 20. MENU THẢ XUỐNG "SAN NỀN" (COM) + MENU DÒNG LỆNH DỰ PHÒNG
;;; ===========================================================================================
(setq *sn-menu*
  '(("BẢNG ĐIỀU KHIỂN TRUNG TÂM… (SN_QL)" "SN_QL")
    ("BẢNG DỌC DOCK NHIỀU TAB (SN_PALETTE)" "SN_PALETTE") "-"
    ("Chọn lô…" "SN_LOT") ("Trạng thái lô" "SN_TRANGTHAI") "-"
    ("Dữ liệu" "SUB"
      ("Nạp dữ liệu (nhập)…" "SN_NHAP") ("Dựng bề mặt TIN (mặt)…" "SN_MAT") ("Chuẩn hóa biên lô…" "SN_LO") "-"
      ("Cảnh báo / QC…" "SN_CANHBAO"))
    ("Xem 3D" "SUB"
      ("Xem bề mặt TIN 3D (polyface)…" "SN_TIN3D") ("Mở trình xem 3D (HTML)" "SN_XEM3D"))
    ("Lưới" "SUB"
      ("Hiệu chỉnh lưới…" "SN_LUOI") ("Đặt lưới & nội suy cao độ đỉnh" "SN_LUOITINH") "-"
      ("Đổi kích thước cột" "SN_DOICOT") ("Đổi kích thước hàng" "SN_DOIHANG")
      ("Chèn cột" "SN_CHENCOT") ("Chèn hàng" "SN_CHENHANG") ("Xóa cột" "SN_XOACOT") ("Xóa hàng" "SN_XOAHANG") "-"
      ("Di chuyển lưới" "SN_DICHLUOI") ("Xoay lưới" "SN_XOAYLUOI"))
    ("Cao độ" "SUB"
      ("Hiệu chỉnh cao độ đỉnh…" "SN_CAPDO") ("Nâng / hạ cao độ thiết kế" "SN_NANGCD") ("Sửa cao độ một đỉnh" "SN_SUADINH") "-"
      ("Đồng bộ nhãn từ bản vẽ" "SN_DONGBO"))
    ("Tính & vẽ" "SUB"
      ("Tính khối lượng đào đắp" "SN_TINH") ("Vẽ lại kết quả" "SN_VE") ("Xóa kết quả trong bản vẽ" "SN_XOA"))
    ("Mặt cắt địa hình…" "SN_MATCAT")
    ("Bảng biểu" "SUB"
      ("Chèn bảng khối lượng…" "SN_BANG") ("Xuất Excel + hồ sơ" "SN_EXCEL"))
    ("Phụ trợ" "SUB"
      ("Cộng ô" "SN_CONGO"))
    "-"
    ("Duyệt cổng…" "SN_DUYET")))

(defun sn:dung-menu (pm items / it sub)                  ; dựng đệ quy các mục menu COM
  (foreach it items
    (cond
      ((equal it "-") (vla-addseparator pm (vla-get-count pm)))
      ((equal (cadr it) "SUB")
       (setq sub (vla-addsubmenu pm (vla-get-count pm) (car it)))
       (sn:dung-menu sub (cddr it)))
      (T (vla-addmenuitem pm (vla-get-count pm) (car it) (strcat (chr 3) (chr 3) (cadr it) " "))))))

(defun sn:tao-menu ( / acad mg pms pm i n it mb)
  ;; Tạo (hoặc dựng lại) menu thả xuống "SAN NỀN" trên thanh menu. Không có AutoCAD giao diện (accoreconsole) → bỏ qua.
  (setq acad (vlax-get-acad-object))
  (if (null acad)
    nil
    (progn
      (setq mg (vla-item (vla-get-menugroups acad) "ACAD")
            pms (vla-get-menus mg)
            pm nil i 0 n (vla-get-count pms))
      (while (< i n)                                      ; dùng lại menu cũ cùng tên để nạp lại không nhân đôi
        (setq it (vla-item pms i))
        (if (= (vla-get-name it) "SAN NỀN") (setq pm it))
        (setq i (1+ i)))
      (if pm
        (progn
          (vl-catch-all-apply 'vla-removefrommenubar (list pm))
          (while (> (vla-get-count pm) 0) (vla-delete (vla-item pm 0))))
        (setq pm (vla-add pms "SAN NỀN")))
      (sn:dung-menu pm *sn-menu*)
      (setq mb (vla-get-menubar acad))
      (vla-insertinmenubar pm (max 0 (1- (vla-get-count mb))))      ; trước menu Help
      T)))

(defun sn:menu-an-toan ( / r)
  (setq r (vl-catch-all-apply 'sn:tao-menu nil))
  (if (vl-catch-all-error-p r)
    (progn (prompt (strcat "\nKhông tạo được menu thả xuống (" (vl-catch-all-error-message r) "). Dùng lệnh SN."))
           nil)
    r))

(defun sn:l-menu ( / k)                                  ; menu dòng lệnh dự phòng — vào được mọi chức năng
  (initget 1 "Quanly Palette Lo Trangthai Nhap Mat Chuanhoa Canhbao Tin3d Luoi Capdo Matcat Tinh Ve Bang Excel Dongbo Congo Duyet Xoa Thoat Xem3d")
  (setq k (getkword (strcat "\nSAN NỀN [Quanly/Palette/Lo/Trangthai/Nhap/Mat/Chuanhoa/Canhbao/Tin3d/Xem3d/Luoi/Capdo/Matcat/Tinh/Ve/Bang/Excel/Dongbo/Congo/Duyet/Xoa/Thoat]: ")))
  (cond
    ((= k "Quanly") (c:SN_QL)) ((= k "Palette") (c:SN_PALETTE))
    ((= k "Lo") (c:SN_LOT)) ((= k "Trangthai") (c:SN_TRANGTHAI)) ((= k "Nhap") (c:SN_NHAP))
    ((= k "Mat") (c:SN_MAT)) ((= k "Chuanhoa") (c:SN_LO)) ((= k "Canhbao") (c:SN_CANHBAO))
    ((= k "Tin3d") (c:SN_TIN3D)) ((= k "Xem3d") (c:SN_XEM3D)) ((= k "Luoi") (c:SN_LUOI)) ((= k "Capdo") (c:SN_CAPDO))
    ((= k "Matcat") (c:SN_MATCAT)) ((= k "Tinh") (c:SN_TINH)) ((= k "Ve") (c:SN_VE))
    ((= k "Bang") (c:SN_BANG)) ((= k "Excel") (c:SN_EXCEL)) ((= k "Dongbo") (c:SN_DONGBO))
    ((= k "Congo") (c:SN_CONGO)) ((= k "Duyet") (c:SN_DUYET)) ((= k "Xoa") (c:SN_XOA))))
(defun c:SN_MENU () (sn:chay-lenh "SN_MENU" 'sn:l-menu))
(defun c:SN () (c:SN_MENU))

;;; ===========================================================================================
;;; 19C. BẢNG DỌC DOCK ĐƯỢC NHIỀU TAB  (SN_PALETTE — add-in .NET cad\dotnet\SanNenPalette)
;;; ===========================================================================================
;;; Palette là add-in C# (DCL không dock được). LISP chỉ: (1) nạp DLL bằng NETLOAD rồi gọi lệnh .NET SN_PALETTE_MO
;;; (tên khác c:SN_PALETTE để không trùng nhau), (2) nhận giá trị từ palette cho hai lệnh GHI có xác nhận (RULES 4):
;;; SN_LUOIAPDUNG (tab Lưới) và SN_XOAMATCAT (tab Mặt cắt). Palette KHÔNG tự ghi gì vào lô.
(setq *sn-pal-nap* nil     ; đã NETLOAD DLL trong phiên này?
      *sn-pal-luoi* nil    ; (cột hàng bù) do palette đặt trước khi gọi SN_LUOIAPDUNG
      *sn-pal-ten* nil)    ; tên mặt cắt do palette đặt trước khi gọi SN_XOAMATCAT

(defun sn:pal-dll ( / cad f)
  (if (setq cad (sn:cfg "cad"))
    (if (findfile (setq f (strcat cad "\\dotnet\\bin\\SanNenPalette.dll"))) f)))

(defun sn:l-palette ( / cad dll)
  (cond
    ((null (setq cad (sn:cfg "cad")))
     (sn:bao (strcat "Chưa cấu hình cad= trong " (sn:cfg-file) " — chạy cad\\cai_dat_cad.ps1.")))
    ((null (setq dll (sn:pal-dll)))
     (sn:bao (strcat "Chưa có SanNenPalette.dll. Xây một lần (ngoài AutoCAD, trong PowerShell): "
                     "powershell -ExecutionPolicy Bypass -File \"" cad "\\dotnet\\xay_palette.ps1\"  rồi gõ lại SN_PALETTE.")))
    (T
     (if (not *sn-pal-nap*)
       (progn
         (sn:bao "Đang nạp palette (NETLOAD). Nếu AutoCAD hỏi tin cậy DLL: chọn Always Load (hoặc thêm thư mục cad\\dotnet\\bin vào TRUSTEDPATHS).")
         (command "_.NETLOAD" dll)
         (setq *sn-pal-nap* T)))
     (command "_.SN_PALETTE_MO"))))
(defun c:SN_PALETTE () (sn:chay-lenh "SN_PALETTE" 'sn:l-palette))

(defun sn:l-luoi-ap-dung ( / v cot hang ns a)
  (if (sn:can-lot)
    (cond
      ((null *sn-pal-luoi*)
       (sn:bao "Chưa có giá trị từ bảng dọc: mở SN_PALETTE → tab Lưới → nhập Cột / Hàng / Bù dữ liệu → Áp dụng."))
      (T
       (setq v *sn-pal-luoi* *sn-pal-luoi* nil
             cot (sn:neu (car v) "") hang (sn:neu (cadr v) "") ns (sn:so (caddr v)))
       (cond
         ((or (null ns) (< ns 0)) (sn:bao "Bù dữ liệu phải là số ≥ 0 (m)."))
         ((sn:xac-nhan (strcat "Áp dụng lưới từ bảng dọc: cột «" cot "», hàng «" hang "», bù dữ liệu " (sn:g ns)
                               " m? (ghi luoi_tuy_chinh.yaml + decisions.md, tính lại và vẽ lại lưới) ") nil)
          (setq a (strcat "--lenh dat --ngoai-suy " (sn:g ns)
                          (if (/= cot "") (strcat " --cot=" (sn:q cot)) "")
                          (if (/= hang "") (strcat " --hang=" (sn:q hang)) "")
                          " --ly-do=" (sn:q "Bảng dọc SN_PALETTE (tab Lưới)")))
          (sn:chay-ve "luoi-sua" a))
         (T (sn:bao "Đã hủy — lưới giữ nguyên.")))))))
(defun c:SN_LUOIAPDUNG () (sn:chay-lenh "SN_LUOIAPDUNG" 'sn:l-luoi-ap-dung))

(defun sn:l-xoamatcat ( / lo dot ten ss i e xd n)         ; xóa BẢN VẼ của một mặt cắt (file số liệu matcat_*.json giữ nguyên)
  (if (sn:can-lot)
    (progn
      (setq lo (sn:ma-lo) dot (sn:dot) ten *sn-pal-ten* *sn-pal-ten* nil)
      (if (or (null ten) (= (sn:cat ten) ""))
        (setq ten (getstring "\nTên mặt cắt cần xóa khỏi bản vẽ: ")))
      (cond
        ((or (null ten) (= (sn:cat ten) "")) (sn:bao "Chưa chọn mặt cắt."))
        ((sn:xac-nhan (strcat "Xóa mặt cắt «" ten "» của lô " lo " khỏi BẢN VẼ này? (số liệu matcat_" ten ".json giữ nguyên) ") nil)
         (setq n 0)
         (if (setq ss (ssget "X" '((-3 ("SANNEN")))))
           (repeat (setq i (sslength ss))
             (setq e (ssname ss (setq i (1- i))) xd (sn:xd-chuoi e))
             (if (and xd (>= (length xd) 4) (= (car xd) lo) (= (cadr xd) (itoa dot)) (= (nth 3 xd) "mat_cat")
                      (= (sn:xd-get xd "ten") ten))
               (progn (entdel e) (setq n (1+ n))))))
         (sn:bao (strcat "Đã xóa " (itoa n) " đối tượng của mặt cắt " ten ".")))
        (T (sn:bao "Đã hủy."))))))
(defun c:SN_XOAMATCAT () (sn:chay-lenh "SN_XOAMATCAT" 'sn:l-xoamatcat))

;;; ===========================================================================================
;;; 21. NẠP
;;; ===========================================================================================
(sn:doc-cfg)
(sn:menu-an-toan)
(prompt (strcat "\nSAN NỀN v" *sn-phien-ban* " đã nạp — gõ SN để mở menu, hoặc dùng menu thả xuống \"SAN NỀN\"."
                (if (sn:cfg "lot") (strcat "\n  Lô hiện tại: " (sn:cfg "lot")) "\n  Chưa chọn lô: gõ SN_LOT.")))
(princ)
