/* Sasenka Loves Food: click-to-enlarge with prev/next navigation. */
(function () {
  // Collect every photo on the page into a single sequence.
  // Order: hero first (if present), then gallery figures top-to-bottom.
  var items = [];

  document.querySelectorAll('.review-hero .photo').forEach(function (photoEl) {
    items.push({
      el: photoEl,
      caption: photoEl.getAttribute('data-caption') || ''
    });
  });
  document.querySelectorAll('.gallery-grid figure').forEach(function (fig) {
    var photoEl = fig.querySelector('.photo');
    var capEl = fig.querySelector('figcaption');
    if (!photoEl) return;
    items.push({
      el: photoEl,
      caption: capEl ? capEl.textContent.trim() : ''
    });
  });

  if (items.length === 0) return;

  var overlay = document.createElement('div');
  overlay.className = 'lightbox';
  overlay.setAttribute('aria-hidden', 'true');
  overlay.innerHTML =
    '<button class="lightbox-close" aria-label="Close">&times;</button>' +
    '<button class="lightbox-nav lightbox-prev" aria-label="Previous photo">&#8249;</button>' +
    '<button class="lightbox-nav lightbox-next" aria-label="Next photo">&#8250;</button>' +
    '<figure class="lightbox-figure">' +
      '<img alt="" />' +
      '<figcaption></figcaption>' +
      '<div class="lightbox-counter"></div>' +
    '</figure>';
  document.body.appendChild(overlay);

  var imgEl = overlay.querySelector('img');
  var capEl = overlay.querySelector('figcaption');
  var counterEl = overlay.querySelector('.lightbox-counter');
  var closeBtn = overlay.querySelector('.lightbox-close');
  var prevBtn = overlay.querySelector('.lightbox-prev');
  var nextBtn = overlay.querySelector('.lightbox-next');

  var currentIndex = -1;

  function sourceFrom(photoEl) {
    var bg = photoEl.style.backgroundImage || '';
    var matches = bg.match(/url\(["']?([^"')]+)["']?\)/g) || [];
    var last = matches[matches.length - 1] || '';
    var m = last.match(/url\(["']?([^"')]+)["']?\)/);
    var src = m ? m[1] : '';
    // Ask Unsplash for a larger version when enlarged
    src = src.replace(/([?&])w=\d+/, '$1w=1600');
    return src;
  }

  function show(index) {
    if (index < 0 || index >= items.length) return;
    currentIndex = index;
    var item = items[index];
    imgEl.src = sourceFrom(item.el);
    imgEl.alt = item.caption || '';
    capEl.textContent = item.caption || '';
    capEl.style.display = item.caption ? 'block' : 'none';
    counterEl.textContent = (index + 1) + ' / ' + items.length;
    prevBtn.disabled = (index === 0);
    nextBtn.disabled = (index === items.length - 1);
  }

  function open(index) {
    show(index);
    overlay.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function close() {
    overlay.setAttribute('aria-hidden', 'true');
    imgEl.src = '';
    currentIndex = -1;
    document.body.style.overflow = '';
  }

  function next() {
    if (currentIndex < items.length - 1) show(currentIndex + 1);
  }
  function prev() {
    if (currentIndex > 0) show(currentIndex - 1);
  }

  items.forEach(function (item, index) {
    item.el.style.cursor = 'zoom-in';
    item.el.addEventListener('click', function (e) {
      e.preventDefault();
      open(index);
    });
  });

  closeBtn.addEventListener('click', function (e) { e.stopPropagation(); close(); });
  prevBtn.addEventListener('click', function (e) { e.stopPropagation(); prev(); });
  nextBtn.addEventListener('click', function (e) { e.stopPropagation(); next(); });

  overlay.addEventListener('click', function (e) {
    // Click on the overlay backdrop closes; clicks on image/caption/buttons do not
    if (e.target === overlay || e.target.classList.contains('lightbox-figure')) close();
  });

  document.addEventListener('keydown', function (e) {
    if (overlay.getAttribute('aria-hidden') !== 'false') return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') prev();
    else if (e.key === 'ArrowRight') next();
  });

  // Basic swipe support on touch devices
  var touchStartX = null;
  overlay.addEventListener('touchstart', function (e) {
    touchStartX = e.touches[0].clientX;
  });
  overlay.addEventListener('touchend', function (e) {
    if (touchStartX === null) return;
    var dx = e.changedTouches[0].clientX - touchStartX;
    if (dx > 50) prev();
    else if (dx < -50) next();
    touchStartX = null;
  });
})();
