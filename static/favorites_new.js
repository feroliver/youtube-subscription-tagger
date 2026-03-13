(function () {
    const dataNode = document.getElementById('favorites-videos-data');
    if (!dataNode) return;

    let allVideos = [];
    try {
        allVideos = JSON.parse(dataNode.textContent || '[]');
    } catch (error) {
        console.error('No se pudo parsear favorites-videos-data', error);
        allVideos = [];
    }

    const placeholderSrc = dataNode.dataset.placeholder || '';
    const buttons = Array.from(document.querySelectorAll('.favorites-view-button'));
    const resultsContainer = document.getElementById('favorites-results');
    const totalVideosEl = document.getElementById('total-new-videos');
    const totalChannelsEl = document.getElementById('total-channels');

    function parseDate(video) {
        return new Date(video.published_at || 0);
    }

    function isInLastDays(video, days) {
        const published = parseDate(video);
        if (Number.isNaN(published.getTime())) {
            return false;
        }
        const threshold = new Date();
        threshold.setUTCDate(threshold.getUTCDate() - days);
        return published >= threshold;
    }

    function buildSections(viewMode) {
        if (viewMode === 'date_desc') {
            return [{
                title: 'Todos los canales (más recientes primero)',
                videos: [...allVideos].sort((a, b) => parseDate(b) - parseDate(a))
            }];
        }

        if (viewMode === 'date_asc') {
            return [{
                title: 'Todos los canales (más antiguos primero)',
                videos: [...allVideos].sort((a, b) => parseDate(a) - parseDate(b))
            }];
        }

        if (viewMode === 'last_7_days' || viewMode === 'last_30_days') {
            const days = viewMode === 'last_7_days' ? 7 : 30;
            return [{
                title: `Todos los canales (últimos ${days} días, del más viejo al más nuevo)`,
                videos: allVideos
                    .filter(video => isInLastDays(video, days))
                    .sort((a, b) => parseDate(a) - parseDate(b))
            }];
        }

        const groups = new Map();
        for (const video of allVideos) {
            const channel = video.channel_title || 'Sin canal';
            if (!groups.has(channel)) groups.set(channel, []);
            groups.get(channel).push(video);
        }

        return Array.from(groups.entries())
            .sort((a, b) => a[0].localeCompare(b[0], 'es', { sensitivity: 'base' }))
            .map(([title, videos]) => ({
                title,
                videos: videos.sort((a, b) => parseDate(b) - parseDate(a))
            }));
    }

    function escapeHtml(text) {
        return String(text ?? '')
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    function render(viewMode) {
        const sections = buildSections(viewMode);
        const totalVideos = sections.reduce((acc, section) => acc + section.videos.length, 0);
        const channelCount = new Set(sections.flatMap(section => section.videos).map(video => video.channel_id)).size;

        totalVideosEl.textContent = String(totalVideos);
        totalChannelsEl.textContent = String(channelCount);

        if (!totalVideos) {
            resultsContainer.innerHTML = '<p>No hay videos nuevos para mostrar en este momento.</p>';
            return;
        }

        resultsContainer.innerHTML = sections.map(section => `
            <section class="favorites-channel-group">
                <h2>${section.title} <span>(${section.videos.length})</span></h2>
                <ul class="favorites-video-list">
                    ${section.videos.map(video => `
                        <li class="favorites-video-item">
                            <img src="${video.thumbnail_url || placeholderSrc}" alt="Miniatura de ${escapeHtml(video.title)}" class="favorites-thumbnail">
                            <div class="favorites-video-meta">
                                <a href="${escapeHtml(video.video_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(video.title)}</a>
                                <p>Publicado: ${escapeHtml(video.published_at || '')}</p>
                                ${video.duration_text ? `<p>Duración: ${escapeHtml(video.duration_text)}</p>` : ''}
                            </div>
                        </li>
                    `).join('')}
                </ul>
            </section>
        `).join('');
    }

    buttons.forEach(button => {
        button.addEventListener('click', () => {
            buttons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            render(button.dataset.view);
        });
    });
})();
