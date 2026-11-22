import random
from functools import wraps
from urllib.parse import urlparse

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from models import Badge, Discovery, Spot, User, db

main_bp = Blueprint("main", __name__)

AUDIO_DESCRIPTIONS = {
    1: "水が勢いよく噴き出し、流れ落ちるような音がします。",
    2: "人の話し声や、屋外のにぎわいを感じさせる音がします。",
    3: "動物の鳴き声や、動物園の周囲の環境音が聞こえます。",
    4: "動物の気配と、飼育エリアの周囲の音が聞こえます。",
    5: "風や木の葉のざわめきのような、開けた場所の音がします。",
    6: "澄んだチャイムの音が響きます。",
    7: "鳥のさえずりや、木々に囲まれた場所の環境音が聞こえます。",
    8: "橋の上を通る足音や、周囲の環境音が聞こえます。",
}


def discovered_ids():
    # 図鑑に登録済みのスポットIDだけを集合として返します。
    user_id = session.get("user_id")
    if user_id is None:
        return set()
    return {item.spot_id for item in Discovery.query.filter_by(user_id=user_id).all()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("main.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def next_mission_spot(found_ids):
    # 未発見スポットのうち、最も低いレベルのスポットから出題します。
    candidates = Spot.query.filter(~Spot.id.in_(found_ids)).all() if found_ids else Spot.query.all()
    if not candidates:
        return None
    lowest_level = min(spot.difficulty for spot in candidates)
    return random.choice([spot for spot in candidates if spot.difficulty == lowest_level])


@main_bp.get("/")
def splash():
    # アプリ起動時の入口画面です。
    return render_template("splash.html", user=db.session.get(User, session.get("user_id")))


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or len(email) > 254 or "@" not in email or len(password) < 8:
            flash("メールアドレスと8文字以上のパスワードを入力してください。", "error")
        else:
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                session.clear()
                session["user_id"] = user.id
                return redirect(_safe_next_url())
            flash("メールアドレスまたはパスワードが正しくありません。", "error")
    return render_template("splash.html", user=None, show_login=True)


@main_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        if not email or len(email) > 254 or "@" not in email:
            flash("有効なメールアドレスを入力してください。", "error")
        elif len(password) < 8:
            flash("パスワードは8文字以上で入力してください。", "error")
        elif password != password_confirm:
            flash("確認用パスワードが一致しません。", "error")
        elif User.query.filter_by(email=email).first():
            flash("このメールアドレスは既に使用されています。別のメールアドレスを選択してください。", "error")
        else:
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("main.home"))
    return render_template("splash.html", user=None, show_register=True)


def _safe_next_url():
    destination = request.form.get("next") or request.args.get("next", "")
    parsed = urlparse(destination)
    if destination.startswith("/") and not destination.startswith("//") and not parsed.netloc:
        return destination
    return url_for("main.home")


@main_bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


@main_bp.get("/home")
@login_required
def home():
    # 探索開始ボタンと図鑑への導線を表示します。
    user = db.session.get(User, session["user_id"])
    username = user.email.partition("@")[0] if user else ""
    return render_template("home.html", username=username)


@main_bp.get("/mission")
@login_required
def mission():
    # まだ発見していないスポットから、今日の出題を1件選びます。
    found_ids = discovered_ids()
    spot = next_mission_spot(found_ids)
    session["mission_spot_id"] = spot.id if spot else None
    audio_options = []
    if spot:
        audio_spots = Spot.query.filter(Spot.audio.isnot(None)).order_by(Spot.id.asc()).all()
        # 正解の音を含めた3つを初期候補にし、残りも選択できるようにします。
        decoys = [item for item in audio_spots if item.id != spot.id]
        random.shuffle(decoys)
        selected = [spot] + decoys[:2]
        random.shuffle(audio_spots)
        audio_options = [
            {"id": item.id, "label": f"音声{index + 1}", "audio": item.audio, "description": AUDIO_DESCRIPTIONS.get(item.id, "周囲の環境音が聞こえます。")}
            for index, item in enumerate(audio_spots)
        ]
        selected_ids = [item.id for item in selected]
        random.shuffle(selected_ids)
    else:
        selected_ids = []
    option_by_id = {option["id"]: option for option in audio_options}
    selected_audio_options = [option_by_id[spot_id] for spot_id in selected_ids]
    return render_template("mission.html", spot=spot, selected_audio_options=selected_audio_options)


@main_bp.get("/explore")
@login_required
def explore():
    # ミッションで選ばれたスポットをGPS探索画面へ渡します。
    spot_id = session.get("mission_spot_id")
    spot = Spot.query.get(spot_id) if spot_id else None
    if spot is None:
        # Exploreを直接開いた場合も、未発見スポットを対象にGPSを開始します。
        found_ids = discovered_ids()
        spot = next_mission_spot(found_ids)
        session["mission_spot_id"] = spot.id if spot else None
    selected_audio_options = []
    if spot:
        audio_spots = Spot.query.filter(Spot.audio.isnot(None)).order_by(Spot.id.asc()).all()
        decoys = [item for item in audio_spots if item.id != spot.id]
        random.shuffle(decoys)
        selected_ids = [spot.id] + [item.id for item in decoys[:2]]
        random.shuffle(audio_spots)
        option_by_id = {
            item.id: {"id": item.id, "label": f"音声{index + 1}", "audio": item.audio, "description": AUDIO_DESCRIPTIONS.get(item.id, "周囲の環境音が聞こえます。")}
            for index, item in enumerate(audio_spots)
        }
        random.shuffle(selected_ids)
        selected_audio_options = [option_by_id[item_id] for item_id in selected_ids]
    return render_template("explore.html", spot=spot, selected_audio_options=selected_audio_options)


@main_bp.get("/discover/<int:spot_id>")
@login_required
def discover(spot_id):
    # 到着判定後に呼ばれ、スポットを図鑑へ登録します。
    spot = Spot.query.get_or_404(spot_id)
    is_new = spot_id not in discovered_ids()
    if is_new:
        db.session.add(Discovery(user_id=session["user_id"], spot_id=spot_id))
        db.session.commit()
    return render_template("discover.html", spot=spot, is_new=is_new)


@main_bp.get("/spot/<int:spot_id>")
@login_required
def spot_detail(spot_id):
    # 未発見のスポットは答えが分からないように403で拒否します。
    spot = Spot.query.get_or_404(spot_id)
    if spot_id not in discovered_ids():
        abort(403)
    return render_template("spot_detail.html", spot=spot)


@main_bp.get("/collection")
@login_required
def collection():
    # 全スポットを、発見済みと未発見に分けて図鑑へ渡します。
    found_ids = discovered_ids()
    # レベル順に並べ、同じレベル内はスポット番号の昇順で表示します。
    spots = Spot.query.order_by(Spot.difficulty.asc(), Spot.id.asc()).all()
    return render_template("collection.html", spots=spots, found_ids=found_ids)


@main_bp.get("/badges")
@login_required
def badges():
    # 現在の発見数を使って、バッジの解放状態を表示します。
    found = len(discovered_ids())
    badge_order = {1: 0, 4: 1, 6: 2, 8: 3}
    all_badges = sorted(Badge.query.all(), key=lambda b: badge_order.get(b.unlock_count, 99))
    return render_template("badges.html", badges=all_badges, found=found)


@main_bp.get("/settings")
@login_required
def settings():
    return render_template("settings.html", spots_reset=request.args.get("spots_reset") == "1")


@main_bp.post("/settings/reset-spots")
@login_required
def reset_spots():
    # 図鑑の発見記録をすべて削除し、選択中のミッションもリセットします。
    Discovery.query.filter_by(user_id=session["user_id"]).delete()
    db.session.commit()
    session.pop("mission_spot_id", None)
    return redirect(url_for("main.settings", spots_reset=1))


@main_bp.app_errorhandler(403)
def forbidden(_error):
    return render_template("403.html"), 403
