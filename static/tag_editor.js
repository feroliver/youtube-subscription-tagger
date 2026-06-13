document.addEventListener('DOMContentLoaded', () => {
    const list = document.getElementById('all-unique-tags-list');
    if (!list) return;

    function closeAllPalettes(except) {
        list.querySelectorAll('.color-palette:not(.hidden)').forEach(p => {
            if (p !== except) p.classList.add('hidden');
        });
    }

    function hideOnOutsideClick(event) {
        const open = list.querySelector('.color-palette:not(.hidden)');
        if (!open) return;
        const trigger = open.previousElementSibling;
        if (open.contains(event.target) || (trigger && trigger.contains(event.target))) {
            document.addEventListener('click', hideOnOutsideClick, { once: true, capture: true });
            return;
        }
        open.classList.add('hidden');
    }

    list.addEventListener('click', (event) => {
        if (event.target.classList.contains('tag-clickable')) {
            const palette = event.target.nextElementSibling;
            if (palette && palette.classList.contains('color-palette')) {
                closeAllPalettes(palette);
                palette.classList.toggle('hidden');
                document.addEventListener('click', hideOnOutsideClick, { once: true, capture: true });
            }
        }
    });

    list.addEventListener('click', async (event) => {
        if (!event.target.classList.contains('color-option')) return;
        event.stopPropagation();

        const button = event.target;
        const newColor = button.dataset.color;
        const tagEntry = button.closest('.tag-entry');
        const tagSpan = tagEntry?.querySelector('.tag-display');
        const tag = tagSpan?.dataset.tag;
        const palette = button.closest('.color-palette');
        if (!tag || !newColor || !palette) return;

        palette.classList.add('hidden');

        const currentColor = (window.tagColors || {})[tag] || window.DEFAULT_TAG_COLOR;
        if (currentColor === newColor) return;

        try {
            const response = await fetch(`/api/tags/color/${encodeURIComponent(tag)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ color: newColor }),
            });
            const result = await response.json();

            if (response.ok && result.success) {
                window.tagColors = result.all_colors;
                tagSpan.style.backgroundColor = newColor;
            } else {
                throw new Error(result.message || 'Failed to update color');
            }
        } catch (error) {
            console.error(`Error updating color for tag ${tag}:`, error);
            alert(`Error updating color: ${error.message}`);
        }
    });
});
