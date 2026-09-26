(() => {
  const toast = (message) => {
    const element = document.querySelector('#toast');
    if (!element) return;
    element.textContent = message;
    element.classList.add('show');
    window.setTimeout(() => element.classList.remove('show'), 2600);
  };

  document.querySelectorAll('.play-button').forEach((button) => {
    const audioName = button.dataset.audio;
    const audio = new Audio(`/static/audio/${encodeURIComponent(audioName)}`);

    // 音声の再生状態に合わせて、ボタンのアイコンを切り替えます。
    const showPlayIcon = () => { button.innerHTML = '<i class="bi bi-play-fill"></i>'; };
    const showPauseIcon = () => { button.innerHTML = '<i class="bi bi-pause-fill"></i>'; };
    audio.addEventListener('ended', showPlayIcon);
    audio.addEventListener('error', () => toast('音声ファイルを再生できませんでした'));

    button.addEventListener('click', async () => {
      if (audio.paused) {
        try {
          await audio.play();
          showPauseIcon();
          toast('音を再生しています');
        } catch (_error) {
          toast('音声の再生を開始できませんでした');
        }
      } else {
        audio.pause();
        showPlayIcon();
      }
    });
  });

  const config = window.exploreConfig;
  if (!config || !config.spotId) {
    const emptyMessage = document.querySelector('#location-message');
    if (emptyMessage) emptyMessage.textContent = '探索できるスポットがありません。';
    return;
  }
  const distanceValue = document.querySelector('#distance-value');
  const message = document.querySelector('#location-message');
  const clueLabel = document.querySelector('#distance-clue-label');
  const clue = document.querySelector('#distance-clue-text');
  const revealHintButton = document.querySelector('#reveal-hint-button');
  const exploreHint = document.querySelector('#explore-hint');
  const progress = document.querySelector('#distance-progress');
  const locate = document.querySelector('#locate-button');
  if (revealHintButton && exploreHint) {
    revealHintButton.addEventListener('click', () => {
      const isVisible = !exploreHint.hidden;
      exploreHint.hidden = isVisible;
      revealHintButton.setAttribute('aria-expanded', String(!isVisible));
      revealHintButton.innerHTML = isVisible
        ? '<i class="bi bi-lightbulb"></i> 手掛かり希望'
        : '<i class="bi bi-eye-slash"></i> 手掛かりを隠す';
    });
  }
  if (!navigator.geolocation) {
    if (message) message.textContent = 'このブラウザでは位置情報を利用できません。（ERR005）';
    return;
  }
  const check = (position) => {
    // 位置情報は判定APIへ送るだけで、移動履歴として保存しません。
    fetch('/api/check', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({spot_id: config.spotId, lat: position.coords.latitude, lng: position.coords.longitude, accuracy: position.coords.accuracy}) })
      .then((response) => response.json()).then((result) => {
        if (result.error) throw new Error(`${result.error}（${result.code || 'ERR002'}）`);
        distanceValue.textContent = result.distance;
        if (clueLabel && result.hintLabel) clueLabel.textContent = result.hintLabel;
        if (clue && result.hint) clue.textContent = result.hint;
        distanceValue.classList.remove('distance-gray', 'distance-yellow', 'distance-green', 'distance-azalea');
        progress.classList.remove('distance-gray', 'distance-yellow', 'distance-green', 'distance-azalea');
        const distanceClass = result.distance >= 100 ? 'distance-gray' : result.distance > 50 ? 'distance-yellow' : result.distance > 20 ? 'distance-green' : 'distance-azalea';
        distanceValue.classList.add(distanceClass);
        progress.classList.add(distanceClass);
        progress.style.width = `${Math.max(8, Math.min(100, 100 - result.distance / 2))}%`;
        if (result.within) {
          message.textContent = '発見エリアに到着しました！';
          message.classList.add('text-success');
          window.setTimeout(() => { window.location.href = result.next; }, 800);
        } else if (result.accuracy > 50) { message.textContent = `位置情報の精度が足りません（±${result.accuracy}m）。開けた場所で再試行してください。（ERR004）`; }
        else if (result.distance > 100) { message.textContent = '探索中。音のする方へ歩いてみよう。'; }
        else if (result.distance > 50) { message.textContent = '近づいています。'; }
        else if (result.distance > 20) { message.textContent = 'かなり近いです。'; }
        else { message.textContent = 'すぐ近くです。'; }
      }).catch((error) => { message.textContent = error.message || 'GPSを取得できませんでした。（ERR002）'; });
  };
  const handleLocationError = (error) => {
    const code = error.code === 1 ? 'ERR001' : error.code === 3 ? 'ERR003' : 'ERR002';
    message.textContent = `${error.code === 1 ? '位置情報の利用を許可してください。' : error.code === 3 ? 'GPS取得がタイムアウトしました。' : 'GPSを取得できませんでした。'}（${code}） 再試行してください。`;
  };
  let watchId = null;
  // 初回は即時取得し、その後は移動中の更新を追跡します。
  const locateUser = () => { message.textContent = '現在地を取得しています...'; locate.disabled = true; navigator.geolocation.getCurrentPosition((position) => { locate.disabled = false; check(position); }, (error) => { locate.disabled = false; handleLocationError(error); }, {enableHighAccuracy: true, timeout: 10000, maximumAge: 0}); if (watchId !== null) navigator.geolocation.clearWatch(watchId); watchId = navigator.geolocation.watchPosition(check, handleLocationError, {enableHighAccuracy: true, timeout: 15000, maximumAge: 5000}); };
  locate.addEventListener('click', locateUser);
  locateUser();

  if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('/static/service-worker.js'));
})();
