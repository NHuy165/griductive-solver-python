# Chạy thí nghiệm

## Cách chạy

```powershell
python -m experiments.run_experiments --repetitions 3 --timeout 60
```

Các tùy chọn:

- `--repetitions N`: số lần lặp cho mỗi màn (mặc định `3`).
- `--timeout S`: thời gian chờ cứng cho mỗi lượt, tính bằng giây (mặc định `60`).
- `--levels 1,3,5-7`: chỉ chạy một tập màn.
- `--output-dir PATH`: đổi thư mục đầu ra (mặc định `experiments/results`).
- `--analyze-only`: đọc lại `runs.csv` và tạo lại `summary.csv`.

## Đầu ra

Thư mục `experiments/results/` gồm:

- `runs.csv`: một dòng cho mỗi lượt chạy, kể cả lượt lỗi hoặc timeout.
- `summary.csv`: tổng hợp theo từng màn.
- `environment.json`: phiên bản Python, hệ điều hành, commit, cấu hình chạy.

## Định nghĩa chỉ số

- `load_time_ms`: thời gian `LevelLoader.load_level_from_file`, bao gồm kiểm tra
  hợp lệ và giải thử bên trong bộ nạp.
- `uniqueness_check_ms`: thời gian `LogicAgent.unique_check` trên CNF đầy đủ.
- `runtime_ms`: chỉ đo `LogicAgent.solve_level`.
- `total_time_ms`: tổng ba giai đoạn trên.
- `sat_calls`: số lần gọi `DpllSatSolver.SAT_solve` thực tế trong giai đoạn giải
  và kiểm tra duy nhất.
- `sat_calls_deduction`, `sat_calls_uniqueness`: lần lượt là giai đoạn giải và 
giai đoạn kiểm tra duy nhất, tổng bằng chỉ số trên.
- `sat_calls_estimated`: ước lượng theo
  `count_SAT_solves_from_level_solve` của hệ thống, dùng để đối chiếu.
- `decisions`, `propagations`, `backtracks`: tổng hợp từ sự kiện của mọi lần gọi
  SAT trong các bước suy diễn.
- `deduction_steps`: số bước suy diễn (số sóng mở bài).
- `new_verdicts`: số phán quyết mới được xác nhận trong toàn bộ quá trình giải.
- `initial_clauses`: số mệnh đề CNF của KB công khai ban đầu.
- `full_clauses`: số mệnh đề CNF khi có toàn bộ manh mối và trạng thái mở đầu.
- `clue_clauses_generated`: số mệnh đề manh mối sinh thêm trong quá trình giải.
- `final_kb_clauses`: số mệnh đề của KB tại thời điểm kết thúc.
- `primary_variables`, `auxiliary_variables`: số biến chính và biến phụ.