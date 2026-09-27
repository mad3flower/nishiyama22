import random

from flask import Blueprint, abort, redirect, render_template, request, session, url_for

from models import Badge, Discovery, Spot, db

main_bp = Blueprint("main", __name__)


def discovered_ids():
    # 図鑑に登録済みのスポットIDだけを集合として返します。
    return {item.spot_id for item in Discovery.query.all()}


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
    return render_template("splash.html")


@main_bp.get("/home")
def home():
    # 探索開始ボタンと図鑑への導線を表示します。
    return render_template("home.html")


@main_bp.get("/mission")
def mission():
    # まだ発見していないスポットから、今日の出題を1件選びます。
    found_ids = discovered_ids()
    spot = next_mission_spot(found_ids)
    session["mission_spot_id"] = spot.id if spot else None
    return render_template("mission.html", spot=spot)


@main_bp.get("/explore")
def explore():
    # ミッションで選ばれたスポットをGPS探索画面へ渡します。
    spot_id = session.get("mission_spot_id")
    spot = Spot.query.get(spot_id) if spot_id else None
    if spot is None:
        # Exploreを直接開いた場合も、未発見スポットを対象にGPSを開始します。
        found_ids = discovered_ids()
        spot = next_mission_spot(found_ids)
        session["mission_spot_id"] = spot.id if spot else None
    return render_template("explore.html", spot=spot)


@main_bp.get("/discover/<int:spot_id>")
def discover(spot_id):
    # 到着判定後に呼ばれ、スポットを図鑑へ登録します。
    spot = Spot.query.get_or_404(spot_id)
    is_new = spot_id not in discovered_ids()
    if is_new:
        db.session.add(Discovery(spot_id=spot_id))
        db.session.commit()
    return render_template("discover.html", spot=spot, is_new=is_new)


@main_bp.get("/spot/<int:spot_id>")
def spot_detail(spot_id):
    # 未発見のスポットは答えが分からないように403で拒否します。
    spot = Spot.query.get_or_404(spot_id)
    if spot_id not in discovered_ids():
        abort(403)
    return render_template("spot_detail.html", spot=spot)


@main_bp.get("/collection")
def collection():
    # 全スポットを、発見済みと未発見に分けて図鑑へ渡します。
    found_ids = discovered_ids()
    # レベル順に並べ、同じレベル内はスポット番号の昇順で表示します。
    spots = Spot.query.order_by(Spot.difficulty.asc(), Spot.id.asc()).all()
    return render_template("collection.html", spots=spots, found_ids=found_ids)


@main_bp.get("/badges")
def badges():
    # 現在の発見数を使って、バッジの解放状態を表示します。
    found = len(discovered_ids())
    badge_order = {1: 0, 4: 1, 6: 2, 8: 3}
    all_badges = sorted(Badge.query.all(), key=lambda b: badge_order.get(b.unlock_count, 99))
    return render_template("badges.html", badges=all_badges, found=found)


@main_bp.get("/settings")
def settings():
    return render_template("settings.html", spots_reset=request.args.get("spots_reset") == "1")


@main_bp.post("/settings/reset-spots")
def reset_spots():
    # 図鑑の発見記録をすべて削除し、選択中のミッションもリセットします。
    Discovery.query.delete()
    db.session.commit()
    session.pop("mission_spot_id", None)
    return redirect(url_for("main.settings", spots_reset=1))


@main_bp.app_errorhandler(403)
def forbidden(_error):
    return render_template("403.html"), 403
