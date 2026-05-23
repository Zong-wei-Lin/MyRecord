# -*- coding: utf-8 -*-
import argparse
import os
import socket
import subprocess
import traceback
import uuid
from datetime import datetime, time as dt_time, timedelta

import app.units.Tool as Tool


# Dispatcher（第一批）
# - 同主機同時只跑一個 dispatcher（主機鎖）
# - 逐筆掃 due 任務，依序執行
# - 明確用 commit/rollback 控制狀態一致性


def get_python_executable(python_executable=None):
    """決定 subprocess 要用哪個 python。"""
    if python_executable:
        return python_executable
    env_python = os.getenv("DISPATCHER_PYTHON")
    if env_python:
        return env_python
    fixed_python = r"D:\Python_ENV\Loader\Scripts\python"
    if os.path.exists(fixed_python):
        return fixed_python
    return "python"


def parse_daily_time(value):
    """把 DB 的 daily_time 轉成 datetime.time。"""
    if value is None:
        return dt_time(0, 0, 0)
    if isinstance(value, dt_time):
        return value
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds()) % (24 * 3600)
        hour = total_seconds // 3600
        minute = (total_seconds % 3600) // 60
        second = total_seconds % 60
        return dt_time(hour, minute, second)
    if isinstance(value, str):
        parts = value.split(":")
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return dt_time(hour, minute, second)
    return dt_time(0, 0, 0)


def parse_weekly_days(weekly_days):
    """把 weekly_days（例: 1,2,3）轉成排序後的整數清單。"""
    if not weekly_days:
        return []
    numbers = []
    for part in str(weekly_days).split(","):
        part = part.strip()
        if part.isdigit():
            day = int(part)
            if 1 <= day <= 7:
                numbers.append(day)
    return sorted(set(numbers))


def compute_next_run_at(row, planned_at, now_time):
    """依排程型態（interval/daily/weekly）計算下次時間。"""
    schedule_type = (row.get("schedule_type") or "").lower()

    if schedule_type == "interval":
        minutes = int(row.get("interval_minutes") or 5)
        candidate = planned_at + timedelta(minutes=minutes)
        # 若算出來仍在過去，以現在為基準往後推一個週期，避免同批次無限重撈
        if candidate <= now_time:
            candidate = now_time + timedelta(minutes=minutes)
        return candidate

    if schedule_type == "daily":
        target_time = parse_daily_time(row.get("daily_time"))
        candidate = datetime.combine(now_time.date(), target_time)
        if candidate <= now_time:
            candidate = candidate + timedelta(days=1)
        return candidate

    if schedule_type == "weekly":
        target_time = parse_daily_time(row.get("daily_time"))
        week_days = parse_weekly_days(row.get("weekly_days"))
        if not week_days:
            return now_time + timedelta(days=7)

        for day_offset in range(0, 8):
            candidate_date = now_time.date() + timedelta(days=day_offset)
            if candidate_date.isoweekday() in week_days:
                candidate_dt = datetime.combine(candidate_date, target_time)
                if candidate_dt > now_time:
                    return candidate_dt

        first_day = week_days[0]
        days_ahead = (first_day - now_time.isoweekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return datetime.combine(now_time.date() + timedelta(days=days_ahead), target_time)

    return now_time + timedelta(minutes=5)


def resolve_script_path(file_path, file_name):
    """組合並標準化腳本完整路徑。"""
    joined = os.path.join(str(file_path or ""), str(file_name or ""))
    return os.path.normpath(joined)


def get_loader_root():
    """回傳 Loader 專案根目錄（供 subprocess 的 cwd/PYTHONPATH 使用）。"""
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def switch_database(conn, database_name):
    """切換目前連線所使用的資料庫。"""
    cursor = conn.cursor()
    try:
        cursor.execute("USE {0}".format(database_name))
    finally:
        cursor.close()


def acquire_global_lock(conn, lock_name):
    """嘗試取得主機鎖（不等待）。"""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT GET_LOCK(%s, 0) AS locked", (lock_name,))
        row = cursor.fetchone()
        if not row:
            return False
        return int(row[0] or 0) == 1
    finally:
        cursor.close()


def release_global_lock(conn, lock_name):
    """釋放主機鎖（失敗不擋主流程）。"""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT RELEASE_LOCK(%s) AS released", (lock_name,))
        # mysql-connector 需要把結果讀掉，避免 Unread result found
        cursor.fetchone()
    except Exception:
        pass
    finally:
        cursor.close()


def fetch_next_due(conn, host_name):
    """抓一筆屬於本機且已到期的排程（依 priority）。"""
    cursor = conn.cursor(dictionary=True)
    try:
        sql = """
            SELECT
                s.id AS schedule_id,
                s.task_id,
                s.schedule_name,
                s.schedule_type,
                s.interval_minutes,
                s.daily_time,
                s.weekly_days,
                s.executor_host,
                s.priority,
                s.timeout_seconds,
                s.allow_overlap,
                t.project_name,
                t.file_path,
                t.file_name,
                ss.next_run_at,
                ss.lock_owner,
                ss.lock_until
            FROM loader_schedule s
            INNER JOIN loader_task t ON t.id = s.task_id
            INNER JOIN loader_schedule_state ss ON ss.schedule_id = s.id
            WHERE LOWER(s.executor_host) = LOWER(%s)
              AND s.is_active = 'Y'
              AND t.is_active = 'Y'
              AND ss.next_run_at <= %s
            ORDER BY s.priority ASC, s.id ASC
            LIMIT 1
        """
        cursor.execute(sql, (host_name, datetime.now()))
        return cursor.fetchone()
    finally:
        cursor.close()


def insert_execution_log(
    conn,
    dispatch_batch_id,
    host_name,
    pid,
    schedule_id,
    task_id,
    run_uuid,
    planned_time,
    trigger_time,
    start_time,
    end_time,
    duration_seconds,
    status,
    skip_reason,
    exit_code,
    message,
    output_excerpt,
):
    """寫一筆 execution_log。"""
    cursor = conn.cursor()
    try:
        sql = """
            INSERT INTO loader_execution_log (
                schedule_id,
                task_id,
                run_uuid,
                dispatch_batch_id,
                planned_time,
                trigger_time,
                start_time,
                end_time,
                duration_seconds,
                attempt_no,
                status,
                skip_reason,
                exit_code,
                message,
                output_excerpt,
                host_name,
                pid,
                create_time
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                1, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        cursor.execute(
            sql,
            (
                schedule_id,
                task_id,
                run_uuid,
                dispatch_batch_id,
                planned_time,
                trigger_time,
                start_time,
                end_time,
                duration_seconds,
                status,
                skip_reason,
                exit_code,
                message,
                output_excerpt,
                host_name,
                pid,
                datetime.now(),
            ),
        )
    finally:
        cursor.close()

def update_state_running(conn, schedule_id, planned_at, lock_until, host_name, pid):
    """將 schedule_state 設為 RUNNING，並更新鎖欄位。"""
    cursor = conn.cursor()
    try:
        sql = """
            UPDATE loader_schedule_state
            SET
                last_status = 'RUNNING',
                last_message = NULL,
                last_planned_at = %s,
                lock_owner = %s,
                lock_until = %s,
                update_time = %s
            WHERE schedule_id = %s
        """
        cursor.execute(
            sql,
            (
                planned_at,
                "{0}:{1}".format(host_name, pid),
                lock_until,
                datetime.now(),
                schedule_id,
            ),
        )
    finally:
        cursor.close()

def update_state_finished(conn, schedule_id, status, message, next_run_at, end_time):
    """任務完成後更新狀態，並清除 lock_owner/lock_until。"""
    cursor = conn.cursor()
    try:
        sql = """
            UPDATE loader_schedule_state
            SET
                last_run_at = %s,
                last_success_at = CASE WHEN %s = 'SUCCESS' THEN %s ELSE last_success_at END,
                last_status = %s,
                last_message = %s,
                next_run_at = %s,
                lock_owner = NULL,
                lock_until = NULL,
                update_time = %s
            WHERE schedule_id = %s
        """
        cursor.execute(
            sql,
            (
                end_time,
                status,
                end_time,
                status,
                message,
                next_run_at,
                datetime.now(),
                schedule_id,
            ),
        )
    finally:
        cursor.close()

def update_state_skip_locked(conn, schedule_id, planned_at, message, next_run_at):
    """仍被鎖住時，記 SKIP 並推進 next_run_at。"""
    cursor = conn.cursor()
    try:
        sql = """
            UPDATE loader_schedule_state
            SET
                last_planned_at = %s,
                last_status = 'SKIP',
                last_message = %s,
                next_run_at = %s,
                update_time = %s
            WHERE schedule_id = %s
        """
        cursor.execute(
            sql,
            (
                planned_at,
                message,
                next_run_at,
                datetime.now(),
                schedule_id,
            ),
        )
    finally:
        cursor.close()

def clear_schedule_lock(conn, schedule_id):
    """例外清理用：強制清除 schedule 鎖欄位。"""
    cursor = conn.cursor()
    try:
        sql = """
            UPDATE loader_schedule_state
            SET
                lock_owner = NULL,
                lock_until = NULL,
                update_time = %s
            WHERE schedule_id = %s
        """
        cursor.execute(sql, (datetime.now(), schedule_id))
    finally:
        cursor.close()


def send_alive_compat(metadata_id, start_time, end_time, duration_seconds, message, status):
    """相容舊版 MonitorLoaders send_alive API。"""
    if metadata_id in (None, "", 0):
        return
    try:
        old_status = "Success" if status == "SUCCESS" else "Fail"
        Tool.send_alive(
            int(metadata_id),
            start_time.strftime("%Y-%m-%d %H:%M:%S"),
            end_time.strftime("%Y-%m-%d %H:%M:%S"),
            float(duration_seconds),
            message,
            old_status,
        )
    except Exception as exc:
        print("[WARN] send_alive failed: {0}".format(exc))


def run_one_schedule(conn, row, dispatch_batch_id, host_name, pid, python_executable):
    """執行單筆排程：鎖檢查 -> 執行 -> 寫log -> 更新狀態。"""
    schedule_id = int(row["schedule_id"])
    task_id = int(row["task_id"])
    planned_at = row.get("next_run_at") or datetime.now()
    now_time = datetime.now()

    lock_until = row.get("lock_until")
    allow_overlap = (row.get("allow_overlap") or "N").upper() == "Y"

    # 上一輪還在鎖定且不允許重疊，就直接 skip。
    if lock_until and lock_until > now_time and not allow_overlap:
        run_uuid = str(uuid.uuid4())
        next_run_at = compute_next_run_at(row, planned_at, now_time)
        skip_message = "schedule is locked by {0}".format(row.get("lock_owner") or "unknown")

        insert_execution_log(
            conn=conn,
            dispatch_batch_id=dispatch_batch_id,
            host_name=host_name,
            pid=pid,
            schedule_id=schedule_id,
            task_id=task_id,
            run_uuid=run_uuid,
            planned_time=planned_at,
            trigger_time=now_time,
            start_time=now_time,
            end_time=now_time,
            duration_seconds=0,
            status="SKIP",
            skip_reason="locked",
            exit_code=None,
            message=skip_message,
            output_excerpt="",
        )
        update_state_skip_locked(conn, schedule_id, planned_at, skip_message, next_run_at)
        # SKIP 的 log 與 state 一起 commit。
        conn.commit()
        print("[SKIP] schedule_id={0} reason=locked".format(schedule_id))
        return

    run_uuid = str(uuid.uuid4())
    timeout_seconds = int(row.get("timeout_seconds") or 600)
    lock_deadline = now_time + timedelta(seconds=timeout_seconds)

    # subprocess 前先把狀態寫成 RUNNING。
    update_state_running(conn, schedule_id, planned_at, lock_deadline, host_name, pid)
    conn.commit()

    start_time = datetime.now()
    end_time = start_time
    status = "FAIL"
    exit_code = None
    output_excerpt = ""
    message = ""

    try:
        script_path = resolve_script_path(row.get("file_path"), row.get("file_name"))
        if not os.path.exists(script_path):
            raise FileNotFoundError("script not found: {0}".format(script_path))

        loader_root = get_loader_root()
        env = os.environ.copy()
        existing_path = env.get("PYTHONPATH", "")
        if existing_path:
            env["PYTHONPATH"] = loader_root + os.pathsep + existing_path
        else:
            env["PYTHONPATH"] = loader_root

        # 執行目標腳本，並擷取 stdout/stderr 摘要。
        result = subprocess.run(
            [python_executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=loader_root,
            env=env,
        )

        end_time = datetime.now()
        exit_code = int(result.returncode)
        stdout_text = result.stdout or ""
        stderr_text = result.stderr or ""
        output_excerpt = (stdout_text + "\n" + stderr_text)[:4000]

        if result.returncode == 0:
            status = "SUCCESS"
            message = "OK"
        else:
            status = "FAIL"
            message = (stderr_text or stdout_text or "process exit code != 0").strip()[:1000]

    except Exception as exc:
        end_time = datetime.now()
        status = "FAIL"
        exit_code = -1
        message = str(exc)[:1000]
        output_excerpt = traceback.format_exc()[:4000]

    duration_seconds = (end_time - start_time).total_seconds()
    next_run_at = compute_next_run_at(row, planned_at, datetime.now())

    # execution_log + schedule_state 用同一個交易區塊。
    try:
        insert_execution_log(
            conn=conn,
            dispatch_batch_id=dispatch_batch_id,
            host_name=host_name,
            pid=pid,
            schedule_id=schedule_id,
            task_id=task_id,
            run_uuid=run_uuid,
            planned_time=planned_at,
            trigger_time=now_time,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            status=status,
            skip_reason=None,
            exit_code=exit_code,
            message=message,
            output_excerpt=output_excerpt,
        )
        update_state_finished(conn, schedule_id, status, message, next_run_at, end_time)
        conn.commit()
    except Exception:
        # 任一步驟失敗就 rollback，避免資料半套。
        conn.rollback()
        try:
            # 盡量清掉鎖欄位，避免後續輪次卡住。
            clear_schedule_lock(conn, schedule_id)
            conn.commit()
        except Exception:
            conn.rollback()
        raise

    # metadata_id 欄位已移除，第一批先不回寫舊版 send_alive。
    # send_alive_compat(
    #     metadata_id=metadata_id,
    #     start_time=start_time,
    #     end_time=end_time,
    #     duration_seconds=duration_seconds,
    #     message=message,
    #     status=status,
    # )

    print(
        "[{0}] schedule_id={1} task_id={2} duration={3:.3f}s".format(
            status,
            schedule_id,
            task_id,
            duration_seconds,
        )
    )
    if status != "SUCCESS":
        print(
            "[FAIL-DETAIL] schedule_id={0} exit_code={1} message={2}".format(
                schedule_id,
                exit_code,
                (message or "")[:500],
            )
        )


def run_dispatcher(host_name=None, python_executable=None):
    """本機 dispatcher 主流程（單次 batch）。"""
    current_host = (host_name or socket.gethostname()).strip()
    python_bin = get_python_executable(python_executable)
    dispatch_batch_id = str(uuid.uuid4())
    pid = os.getpid()
    lock_name = "loader_dispatcher_{0}".format(current_host.lower())

    db = Tool.DBConnent("ml350gen8")
    conn = db._connect()
    conn.autocommit = False
    # 目前新排程表在 log_record，不在 DBConnent 預設的 db。
    switch_database(conn, "log_record")

    print("[Dispatcher] host={0} batch={1}".format(current_host, dispatch_batch_id))

    # 避免同主機同時跑多個 dispatcher。
    if not acquire_global_lock(conn, lock_name):
        print("[Dispatcher] skip: host lock not acquired")
        conn.close()
        return 0

    processed = 0
    try:
        # 持續掃描 due 任務，直到這次 batch 清空。
        while True:
            row = fetch_next_due(conn, current_host)
            if not row:
                break

            try:
                run_one_schedule(
                    conn=conn,
                    row=row,
                    dispatch_batch_id=dispatch_batch_id,
                    host_name=current_host,
                    pid=pid,
                    python_executable=python_bin,
                )
                processed += 1
            except Exception as exc:
                # 單筆失敗不終止整批，繼續跑下一筆。
                conn.rollback()
                schedule_id = row.get("schedule_id")
                print("[Dispatcher][ERROR] schedule_id={0} error={1}".format(schedule_id, exc))
                print(traceback.format_exc())

        print("[Dispatcher] done: processed={0}".format(processed))
        return processed
    finally:
        # 不論成功失敗都要釋放主機鎖、關閉連線。
        release_global_lock(conn, lock_name)
        conn.close()


def parse_args():
    """CLI 參數：可覆蓋 host 與 python 路徑。"""
    parser = argparse.ArgumentParser(description="Single host dispatcher (first batch)")
    parser.add_argument("--host", help="override current host name")
    parser.add_argument("--python", dest="python_executable", help="python executable for subprocess")
    return parser.parse_args()


def main():
    """CLI 入口。"""
    args = parse_args()
    run_dispatcher(host_name=args.host, python_executable=args.python_executable)


if __name__ == "__main__":
    main()
