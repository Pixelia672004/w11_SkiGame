"""第11回配布教材：ASCIIスキーゲーム（学生版）。

実行：python w11_ski_demo.py
Windowsで curses が見つからない場合：py -m pip install windows-curses

w11演習01：update_distance_score() の中だけを実装する。
"""

import random
import time
from collections import deque

try:
    import curses
except ImportError:
    raise SystemExit(
        "curses を読み込めません。Windowsでは "
        "'py -m pip install windows-curses' を実行してください。"
    )


# 画面とゲームの基本設定
FPS = 30
MIN_COLUMNS = 64
MIN_LINES = 21
MAX_FIELD_WIDTH = 68
FIELD_TOP = 3
STATUS_READY = "READY"
STATUS_PLAYING = "PLAYING"
STATUS_PAUSED = "PAUSED"
STATUS_GAME_OVER = "GAME_OVER"


def clamp(value, minimum, maximum):
    """値が指定範囲からはみ出さないようにする。"""
    return max(minimum, min(value, maximum))


def create_state(field_width, field_height, rng):
    """新しいゲームを開始するためのStateを用意する。"""
    half_width = min(19, max(13, (field_width - 12) // 2))
    state = {
        "status": STATUS_READY,
        "x": field_width // 2,
        "y": max(3, int(field_height * 0.35)),
        "direction": 1,     # -1: 左、+1: 右。直進（0）は使わない。
        "speed": 1.0,
        "elapsed_time": 0.0,   # 一時停止中は増えない
        "scroll_count": 0,    # コースが進んだ行数
        "score": 0,           # w11演習01で更新する
        "level": 1,           # 100行進むごとに上昇
        "scroll_progress": 0.0,
        "field_width": field_width,
        "field_height": field_height,
        "course_center": field_width // 2,
        "course_half_width": half_width,
        "rows": deque(),
        "game_over_reason": "",
    }

    # 開始直後の画面は障害物なし。新しく現れるコースから木を生成する。
    for _ in range(field_height):
        state["rows"].append(create_course_row(state, rng, with_tree=False))
    return state


def create_course_row(state, rng, with_tree=True):
    """コースを1行生成する。木や崖の生成は講師提供部分。"""
    width = state["field_width"]
    half = state["course_half_width"]

    # 崖の幅とコース中心を急激に変化させず、通れる幅を確保する。
    if rng.random() < 0.13:
        half = int(clamp(half + rng.choice([-1, 1]), 13, 21))
    center = state["course_center"] + rng.choice([-1, 0, 0, 0, 0, 1])
    center = int(clamp(center, half + 3, width - half - 4))
    state["course_center"] = center
    state["course_half_width"] = half

    left = center - half
    right = center + half
    tree = None
    tree_rate = min(0.52, 0.23 + (state["level"] - 1) * 0.055)
    if with_tree and rng.random() < tree_rate:
        tree = rng.randint(left + 3, right - 3)

    return {"left": left, "right": right, "tree": tree}


def update_distance_score(state):
    """w11演習01：コースが1行進んだときに、1回だけ呼び出される。"""
    # TODO: Stateの score に1点加算する処理を1行書こう。
    # ヒント：第4章で学んだ辞書の値の更新を利用する。
    pass


def move_course_one_row(state, rng):
    """コースを1行スクロールさせ、距離とレベルを更新する。"""
    # 新しいコースは画面の上に現れ、下（プレイヤー側）へ流れる。
    state["rows"].pop()
    state["rows"].appendleft(create_course_row(state, rng))

    # 直進はできない。1行進むごとに必ず左右どちらかへ1文字移動する。
    state["x"] += state["direction"]
    state["scroll_count"] += 1
    state["level"] = state["scroll_count"] // 100 + 1

    # 演習対象の関数は「1行進むたび」に呼ばれる。
    update_distance_score(state)


def check_collision(state):
    """現在のプレイヤー位置に崖または木があるか判定する。"""
    player_x = int(round(state["x"]))
    row = state["rows"][state["y"]]
    if player_x <= row["left"] or player_x >= row["right"]:
        state["game_over_reason"] = "CLIFF!"
        state["status"] = STATUS_GAME_OVER
    elif row["tree"] == player_x:
        state["game_over_reason"] = "TREE!"
        state["status"] = STATUS_GAME_OVER


def update_game(state, dt, rng):
    """プレイ中だけ時間・位置・コースを更新する。"""
    if state["status"] != STATUS_PLAYING:
        return

    state["elapsed_time"] += dt
    state["speed"] = 1.0 + (state["level"] - 1) * 0.15

    # 毎フレームではなく、実際に1行進んだときだけ位置と距離を更新する。
    state["scroll_progress"] += 3.0 * state["speed"] * dt
    while state["scroll_progress"] >= 1.0 and state["status"] == STATUS_PLAYING:
        state["scroll_progress"] -= 1.0
        move_course_one_row(state, rng)
        check_collision(state)


def read_key(state, key):
    """キー入力をStateへ反映する。再起動要求なら True を返す。"""
    if key in (ord("q"), ord("Q")):
        return "QUIT"
    if state["status"] == STATUS_GAME_OVER and key in (ord("r"), ord("R")):
        return "RESTART"
    if key == ord(" "):
        if state["status"] in (STATUS_READY, STATUS_PAUSED):
            state["status"] = STATUS_PLAYING
        elif state["status"] == STATUS_PLAYING:
            state["status"] = STATUS_PAUSED
        return None
    if state["status"] == STATUS_PLAYING:
        # 進行方向は左(-1)か右(+1)の二択。
        # 連打しても旋回は強くならない。
        if key == curses.KEY_LEFT:
            state["direction"] = -1
        elif key == curses.KEY_RIGHT:
            state["direction"] = 1
    return None


def draw_line(screen, y, text, style=0):
    """右下隅への書き込みによるcursesエラーを避けて表示する。"""
    rows, cols = screen.getmaxyx()
    if 0 <= y < rows - 1 and cols >= 2:
        screen.addnstr(y, 1, str(text), cols - 2, style)


def draw_game(screen, state):
    """Stateの内容を読み取り、文字で画面を再描画する。"""
    screen.erase()
    rows, cols = screen.getmaxyx()
    width = state["field_width"]
    offset = (cols - width) // 2

    t = state["elapsed_time"]
    mins, seconds = divmod(int(t), 60)
    hud = (
        f"LV {state['level']:02d} | SCORE {state['score']:05d} | "
        f"DIST {state['scroll_count']:05d} | TIME {mins:02d}:{seconds:02d}"
    )
    turn = "LEFT" if state["direction"] == -1 else "RIGHT"
    info = f"SPEED {state['speed']:.2f}x | TURN {turn} | STATE {state['status']}"
    draw_line(screen, 0, hud, curses.A_BOLD)
    draw_line(screen, 1, info)
    screen.addnstr(2, offset, "=" * width, width)

    player_x = int(round(state["x"]))
    for i, row in enumerate(state["rows"]):
        chars = [" "] * width
        for x in range(0, row["left"] + 1):
            chars[x] = "*"
        for x in range(row["right"], width):
            chars[x] = "*"
        if row["tree"] is not None:
            chars[row["tree"]] = "A"
        if i == state["y"] and 0 <= player_x < width:
            chars[player_x] = "X" if state["status"] == STATUS_GAME_OVER else "O"
        screen.addnstr(FIELD_TOP + i, offset, "".join(chars), width)

    if state["status"] == STATUS_READY:
        message = "READY! Press SPACE to start"
    elif state["status"] == STATUS_PAUSED:
        message = "PAUSED - Press SPACE to resume"
    elif state["status"] == STATUS_GAME_OVER:
        message = f"GAME OVER ({state['game_over_reason']}) - R to restart"
    else:
        message = "Avoid trees (A) and cliffs (*)!"
    draw_line(screen, rows - 3, message, curses.A_BOLD)
    draw_line(screen, rows - 2, "LEFT/RIGHT: switch turn | SPACE: start/pause | R: restart | Q: quit")
    screen.refresh()


def run(screen):
    """ゲーム全体のループ。"""
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    screen.keypad(True)
    screen.nodelay(True)

    rng = random.Random()
    state = None
    current_size = None
    last_time = time.monotonic()

    while True:
        now = time.monotonic()
        dt = min(0.10, now - last_time)
        last_time = now
        height, width = screen.getmaxyx()
        key = screen.getch()

        if key in (ord("q"), ord("Q")):
            break
        if width < MIN_COLUMNS or height < MIN_LINES:
            screen.erase()
            draw_line(screen, 1, f"Terminal too small: {width}x{height}")
            draw_line(screen, 3, f"Please enlarge to {MIN_COLUMNS}x{MIN_LINES} or more.")
            draw_line(screen, 5, "Press Q to quit.")
            screen.refresh()
            state = None
            current_size = None
            time.sleep(1.0 / FPS)
            continue

        size = (height, width)
        if state is None or size != current_size:
            field_width = min(MAX_FIELD_WIDTH, width - 4)
            field_height = height - 7
            state = create_state(field_width, field_height, rng)
            current_size = size

        command = read_key(state, key)
        if command == "QUIT":
            break
        if command == "RESTART":
            state = create_state(state["field_width"], state["field_height"], rng)
            state["status"] = STATUS_PLAYING

        update_game(state, dt, rng)
        draw_game(screen, state)
        time.sleep(1.0 / FPS)


def main():
    try:
        curses.wrapper(run)
    except curses.error as error:
        print("ターミナルの表示に失敗しました。VS Codeの『ターミナル』で実行してください。")
        print("ターミナルの幅・高さも確認してください。")
        print(f"詳細: {error}")


if __name__ == "__main__":
    main()
