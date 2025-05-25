document.addEventListener('DOMContentLoaded', () => {
    const channelListContainer = document.getElementById('channels-container');
    const tagFilterList = document.getElementById('tag-filter-list');
    const allUniqueTagsList = document.getElementById('all-unique-tags-list');
    const channelCountSpan = document.getElementById('channel-count');
    const refreshButton = document.getElementById('refresh-button');
    const refreshStatus = document.getElementById('refresh-status');
    const interactiveTagList = document.getElementById('all-unique-tags-list'); // Referencia a la lista de tags interactiva
    const searchInput = document.getElementById('channel-search');

    // Obtener la lista de tags únicos del DOM
    const uniqueTags = Array.from(allUniqueTagsList.querySelectorAll('.tag-display'))
        .map(span => span.textContent.trim());

    // Función para manejar el autocompletado
    function setupTagAutocomplete(inputElement) {
        let currentSuggestion = '';
        let suggestionSpan = null;

        function createSuggestionSpan() {
            if (!suggestionSpan) {
                suggestionSpan = document.createElement('span');
                suggestionSpan.style.position = 'absolute';
                suggestionSpan.style.color = '#999';
                suggestionSpan.style.pointerEvents = 'none';
                inputElement.parentNode.style.position = 'relative';
                inputElement.parentNode.appendChild(suggestionSpan);
            }
        }

        function updateSuggestion() {
            const inputValue = inputElement.value;
            const lastTag = inputValue.split(',').pop().trim();
            
            if (lastTag) {
                const matchingTag = uniqueTags.find(tag => 
                    tag.toLowerCase().startsWith(lastTag.toLowerCase()) && 
                    tag.toLowerCase() !== lastTag.toLowerCase()
                );

                if (matchingTag) {
                    createSuggestionSpan();
                    currentSuggestion = matchingTag;
                    suggestionSpan.textContent = inputValue.slice(0, -lastTag.length) + matchingTag;
                    suggestionSpan.style.left = inputElement.offsetLeft + 'px';
                    suggestionSpan.style.top = inputElement.offsetTop + 'px';
                    suggestionSpan.style.padding = window.getComputedStyle(inputElement).padding;
                    suggestionSpan.style.font = window.getComputedStyle(inputElement).font;
                    suggestionSpan.style.display = 'block';
                } else {
                    if (suggestionSpan) {
                        suggestionSpan.style.display = 'none';
                    }
                    currentSuggestion = '';
                }
            } else {
                if (suggestionSpan) {
                    suggestionSpan.style.display = 'none';
                }
                currentSuggestion = '';
            }
        }

        function acceptSuggestion() {
            if (currentSuggestion) {
                const inputValue = inputElement.value;
                const lastTag = inputValue.split(',').pop().trim();
                inputElement.value = inputValue.slice(0, -lastTag.length) + currentSuggestion;
                if (suggestionSpan) {
                    suggestionSpan.style.display = 'none';
                }
                currentSuggestion = '';
            }
        }

        inputElement.addEventListener('input', updateSuggestion);
        inputElement.addEventListener('keydown', (e) => {
            if (e.key === 'Tab' && currentSuggestion) {
                e.preventDefault();
                acceptSuggestion();
            }
        });
    }

    // Aplicar autocompletado a todos los inputs de tags existentes
    document.querySelectorAll('.tag-input-section input[type="text"]').forEach(setupTagAutocomplete);

    // Aplicar autocompletado a nuevos inputs cuando se creen
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) { // Element node
                    const newInputs = node.querySelectorAll('.tag-input-section input[type="text"]');
                    newInputs.forEach(setupTagAutocomplete);
                }
            });
        });
    });

    observer.observe(channelListContainer, { childList: true, subtree: true });

    // --- Helper Functions ---

    // Función para obtener el color de un tag (usa el mapa global y el default)
    function getTagColor(tag) {
        return window.tagColors?.[tag] || window.DEFAULT_TAG_COLOR || '#cccccc';
    }

    // Función para escapar HTML (simple)
    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
     }

    // Función para actualizar visualmente el color de todos los tags con un nombre específico
    function updateTagColorOnPage(tag, newColor) {
        // Actualizar span en la lista interactiva de la sidebar
         const sidebarTagSpan = interactiveTagList?.querySelector(`.tag-display[data-tag="${CSS.escape(tag)}"]`);
         if (sidebarTagSpan) sidebarTagSpan.style.backgroundColor = newColor;

         // Actualizar botón de filtro
         const filterButton = tagFilterList?.querySelector(`.tag-filter[data-tag="${CSS.escape(tag)}"]`);
         if (filterButton) {
              filterButton.style.backgroundColor = newColor;
              filterButton.style.borderColor = newColor; // También el borde si es relevante
         }

         // Actualizar spans en las tarjetas de canal (iterando)
         channelListContainer?.querySelectorAll(`.channel-card .tag-display`).forEach(span => {
             if (span.textContent === tag) { // Compara el texto dentro del span
                 span.style.backgroundColor = newColor;
             }
         });
    }

    // Actualiza la sección de tags de UN canal específico
    function updateChannelTagsDisplay(channelId, tags) {
        const tagsContainer = document.getElementById(`tags-${channelId}`);
        if (!tagsContainer) return;

        tagsContainer.innerHTML = ''; // Clear existing tags
        tags.forEach(tag => {
            const span = document.createElement('span');
            span.className = 'tag-display';
            span.textContent = tag;
            span.style.backgroundColor = getTagColor(tag); // Aplicar color
            tagsContainer.appendChild(span);
        });

        // Also update the input field to reflect the saved state (cleaned tags)
        const inputElement = document.getElementById(`input-${channelId}`);
        if(inputElement) {
             inputElement.value = tags.join(', ');
        }
    }

    // Actualiza la lista de botones de filtro y la lista interactiva de tags
    function updateTagFilters(uniqueTags) {
        if (!tagFilterList || !allUniqueTagsList) return;

        // --- Update Filter Buttons ---
        const currentActiveButtons = Array.from(tagFilterList.querySelectorAll('.tag-filter.selected'))
            .map(button => button.dataset.tag);

        tagFilterList.innerHTML = ''; // Clear existing filter buttons

        // Add "Show All" button
        const allButton = document.createElement('button');
        allButton.className = 'tag-filter';
        allButton.dataset.tag = 'all';
        allButton.textContent = 'Show All';
        allButton.style.backgroundColor = '#e0e0e0';
        allButton.style.borderColor = '#e0e0e0';
        if (currentActiveButtons.includes('all')) {
            allButton.classList.add('selected');
        }
        tagFilterList.appendChild(allButton);

        // Add "No Tags" button
        const noTagButton = document.createElement('button');
        noTagButton.className = 'tag-filter';
        noTagButton.dataset.tag = 'no-tag';
        noTagButton.textContent = 'No Tags';
        noTagButton.style.backgroundColor = '#ff6b6b';
        noTagButton.style.borderColor = '#ff6b6b';
        if (currentActiveButtons.includes('no-tag')) {
            noTagButton.classList.add('selected');
        }
        tagFilterList.appendChild(noTagButton);

        // Add buttons for each unique tag
        uniqueTags.forEach(tag => {
            const button = document.createElement('button');
            const color = getTagColor(tag);
            button.className = 'tag-filter';
            button.dataset.tag = tag;
            button.textContent = tag;
            button.style.backgroundColor = color;
            button.style.borderColor = color;
            if (currentActiveButtons.includes(tag)) {
                button.classList.add('selected');
            }
            tagFilterList.appendChild(button);
        });

        // Restore multi-selected state if needed
        if (currentActiveButtons.length > 1) {
            tagFilterList.querySelectorAll('.tag-filter.selected').forEach(button => {
                button.classList.add('multi-selected');
            });
        }

         // --- Update "All Unique Tags" Interactive Display List ---
         allUniqueTagsList.innerHTML = ''; // Clear existing tags
         uniqueTags.forEach(tag => {
            const color = getTagColor(tag);
            const tagEntryDiv = document.createElement('div');
            tagEntryDiv.className = 'tag-entry';

            const tagSpan = document.createElement('span');
            tagSpan.className = 'tag-display tag-clickable';
            tagSpan.dataset.tag = tag;
            tagSpan.style.backgroundColor = color;
            tagSpan.textContent = tag;

            const paletteDiv = document.createElement('div');
            paletteDiv.className = 'color-palette hidden';
            paletteDiv.innerHTML = `
                <button class="color-option" data-color="#ffadad" style="background-color:#ffadad;" title="#ffadad"></button>
                <button class="color-option" data-color="#ffd6a5" style="background-color:#ffd6a5;" title="#ffd6a5"></button>
                <button class="color-option" data-color="#fdffb6" style="background-color:#fdffb6;" title="#fdffb6"></button>
                <button class="color-option" data-color="#caffbf" style="background-color:#caffbf;" title="#caffbf"></button>
                <button class="color-option" data-color="#9bf6ff" style="background-color:#9bf6ff;" title="#9bf6ff"></button>
                <button class="color-option" data-color="#a0c4ff" style="background-color:#a0c4ff;" title="#a0c4ff"></button>
                <button class="color-option" data-color="#bdb2ff" style="background-color:#bdb2ff;" title="#bdb2ff"></button>
                <button class="color-option" data-color="#ffc6ff" style="background-color:#ffc6ff;" title="#ffc6ff"></button>
                <button class="color-option" data-color="${window.DEFAULT_TAG_COLOR || '#cccccc'}" style="background-color:${window.DEFAULT_TAG_COLOR || '#cccccc'};" title="Default Color">Reset</button>
            `;

            tagEntryDiv.appendChild(tagSpan);
            tagEntryDiv.appendChild(paletteDiv);
            allUniqueTagsList.appendChild(tagEntryDiv);
         });
    }

    // Filtra los canales visibles basado en los tags seleccionados
    function filterChannelsByTag() {
        if (!channelListContainer) return;
        const cards = channelListContainer.querySelectorAll('.channel-card');
        let visibleCount = 0;

        // Obtener todos los tags seleccionados
        const selectedTags = Array.from(tagFilterList.querySelectorAll('.tag-filter.selected'))
            .map(button => button.dataset.tag);

        // Si no hay tags seleccionados o solo está seleccionado "all", mostrar todos
        if (selectedTags.length === 0 || (selectedTags.length === 1 && selectedTags[0] === 'all')) {
            cards.forEach(card => {
                card.classList.remove('hidden');
                visibleCount++;
            });
        } else {
        cards.forEach(card => {
            let tagsOnCard = [];
            try {
                 const tagsData = card.dataset.tags;
                 tagsOnCard = tagsData ? JSON.parse(tagsData) : [];
                 if (!Array.isArray(tagsOnCard)) tagsOnCard = [];
            } catch (e) {
                 console.error("Error parsing tags data from card:", card.dataset.tags, e);
                 tagsOnCard = [];
            }

                // Verificar si el canal tiene TODOS los tags seleccionados
                const hasAllSelectedTags = selectedTags.every(tag => {
                    if (tag === 'no-tag') {
                        return tagsOnCard.length === 0;
                    }
                    return tagsOnCard.includes(tag);
                });

                if (hasAllSelectedTags) {
                card.classList.remove('hidden');
                visibleCount++;
            } else {
                card.classList.add('hidden');
            }
        });
        }

        if (channelCountSpan) {
             channelCountSpan.textContent = visibleCount;
        }
    }

    // Redibuja la lista COMPLETA de canales (usado después de refresh)
    function updateChannelList(channels) {
         if (!channelListContainer) return;
         channelListContainer.innerHTML = ''; // Clear existing channels

        if (!channels || channels.length === 0) {
             channelListContainer.innerHTML = '<p>No channels found.</p>';
             if (channelCountSpan) channelCountSpan.textContent = '0';
             return;
        }

         channels.forEach(channel => {
             const card = document.createElement('div');
             card.className = 'channel-card';
             card.dataset.channelId = channel.channel_id;
             card.dataset.tags = JSON.stringify(channel.tags || []); // Store tags as JSON string

             const tagsHtml = (channel.tags || [])
                 .map(tag => `<span class="tag-display" style="background-color: ${getTagColor(tag)};">${escapeHtml(tag)}</span>`)
                 .join('');
             const tagsValue = (channel.tags || []).join(', ');

             // Usar placeholder si no hay thumbnail
             const thumbnailUrl = channel.thumbnail_url || "{{ url_for('static', filename='placeholder.png') }}"; // Asume que tienes placeholder.png en static

             card.innerHTML = `
                <img src="${thumbnailUrl}" alt="${escapeHtml(channel.title)} thumbnail" class="thumbnail">
                <div class="channel-info">
                    <h3>
                        <a href="https://www.youtube.com/channel/${channel.channel_id}" target="_blank" rel="noopener noreferrer" title="Visit channel on YouTube">
                            ${escapeHtml(channel.title)}
                        </a>
                    </h3>
                    <div class="current-tags" id="tags-${channel.channel_id}">${tagsHtml}</div>
                    <div class="tag-input-section">
                        <input type="text" id="input-${channel.channel_id}" placeholder="Add tags (comma-separated)" value="${escapeHtml(tagsValue)}">
                        <button class="save-tags-button" data-channel-id="${channel.channel_id}">Save Tags</button>
                        <span class="status-message" id="status-${channel.channel_id}"></span>
                    </div>
                </div>
             `;
             channelListContainer.appendChild(card);
         });

        if (channelCountSpan) {
            channelCountSpan.textContent = channels.length;
        }
    }


    // --- Event Listeners ---

    // Event delegation for saving tags
    if (channelListContainer) {
        channelListContainer.addEventListener('click', async (event) => {
            if (event.target.classList.contains('save-tags-button')) {
                const button = event.target;
                const channelId = button.dataset.channelId;
                const inputElement = document.getElementById(`input-${channelId}`);
                const tagsString = inputElement.value.trim();
                const statusElement = document.getElementById(`status-${channelId}`);

                button.disabled = true;
                statusElement.textContent = 'Saving...';
                statusElement.className = 'status-message';

                try {
                    const response = await fetch(`/api/tags/${channelId}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ tags: tagsString }),
                    });
                    const result = await response.json();

                    if (response.ok && result.success) {
                        window.tagColors = result.tag_colors;
                        updateChannelTagsDisplay(channelId, result.tags);
                        const card = button.closest('.channel-card');
                        if(card) card.dataset.tags = JSON.stringify(result.tags);
                        
                        // Preserve current filter state
                        const currentActiveButtons = Array.from(tagFilterList.querySelectorAll('.tag-filter.selected'))
                            .map(button => button.dataset.tag);
                        
                        updateTagFilters(result.unique_tags);
                        
                        // Re-apply current filter
                        filterChannelsByTag();
                        
                        statusElement.textContent = 'Saved!';
                        statusElement.classList.add('success');
                    } else {
                        throw new Error(result.message || 'Failed to save tags.');
                    }
                } catch (error) {
                    console.error('Error saving tags:', error);
                    statusElement.textContent = `Error: ${error.message}`;
                    statusElement.classList.add('error');
                } finally {
                    button.disabled = false;
                    setTimeout(() => {
                         if (statusElement.textContent === 'Saved!' || statusElement.textContent.startsWith('Error:')) {
                              statusElement.textContent = '';
                              statusElement.className = 'status-message';
                         }
                    }, 3000);
                }
            }
        });

        // Allow pressing Enter in tag input to save
        channelListContainer.addEventListener('keypress', (event) => {
             if (event.key === 'Enter' && event.target.tagName === 'INPUT' && event.target.id.startsWith('input-')) {
                 event.preventDefault();
                 const channelId = event.target.id.split('-')[1];
                 const saveButton = channelListContainer.querySelector(`.save-tags-button[data-channel-id="${channelId}"]`);
                 if (saveButton) saveButton.click();
             }
        });

        // --- NEW: Event delegation for rating stars ---
        channelListContainer.addEventListener('click', async (event) => {
            const star = event.target.closest('.star');
            const clearButton = event.target.closest('.clear-rating');
            const ratingContainer = event.target.closest('.rating-stars');

            if (!ratingContainer || (!star && !clearButton)) {
                 return; // Click wasn't on a star or the clear button inside a rating container
            }

            const channelId = ratingContainer.dataset.channelId;
            let newRating = null;

            if (star) {
                 newRating = parseInt(star.dataset.value, 10);
            } else if (clearButton) {
                 newRating = null; // Signal to clear the rating
            }

            // Prevent sending update if rating didn't change (e.g., clicking current rating)
            // This check might be optional depending on desired UX
            // const currentRating = Array.from(ratingContainer.querySelectorAll('.star.filled')).length;
            // if (newRating === currentRating) return;

            // Visually provide immediate feedback (optional, could wait for server response)
            // updateStarsVisual(ratingContainer, newRating);

            try {
                const response = await fetch(`/api/rating/${channelId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rating: newRating }), // Send null to clear
                });
                const result = await response.json();

                if (response.ok && result.success) {
                    console.log(`Rating updated for ${channelId} to ${result.rating}`);
                    // Update stars definitively based on server response
                    updateStarsVisual(ratingContainer, result.rating);

                    // OPTIONAL: Re-render the entire channel list to reflect the new order
                    // This is simpler than trying to reorder elements in the DOM
                    // updateChannelList(result.channels);
                    // updateTagFilters(result.unique_tags); // Might need tags if re-rendering
                    // Be aware this might lose scroll position etc.

                    // Simpler: Just update the visual stars, order updates on next full page load/refresh

                } else {
                    throw new Error(result.message || 'Failed to update rating.');
                    // Revert visual change if immediate feedback was given
                    // updateStarsVisual(ratingContainer, currentRating); // Revert to original
                }
            } catch (error) {
                console.error('Error updating rating:', error);
                alert(`Error updating rating: ${error.message}`);
                // Revert visual change if immediate feedback was given
                // updateStarsVisual(ratingContainer, currentRating); // Revert to original
            }
        });
        // --- END NEW: Event delegation for rating stars ---

    // Event listener for tag filtering
    if (tagFilterList) {
        tagFilterList.addEventListener('click', (event) => {
            if (event.target.classList.contains('tag-filter')) {
                    const clickedTag = event.target.dataset.tag;
                    
                    // Si se hace clic en "all", deseleccionar todo lo demás
                    if (clickedTag === 'all') {
                        tagFilterList.querySelectorAll('.tag-filter').forEach(button => {
                            button.classList.remove('selected', 'multi-selected');
                        });
                        event.target.classList.add('selected');
                    } else {
                        // Si se hace clic en otro tag, deseleccionar "all"
                        const allButton = tagFilterList.querySelector('.tag-filter[data-tag="all"]');
                        if (allButton) {
                            allButton.classList.remove('selected');
                        }
                        
                        // Alternar la selección del tag clickeado
                        event.target.classList.toggle('selected');
                        
                        // Actualizar el estado de multi-selected
                        const selectedCount = tagFilterList.querySelectorAll('.tag-filter.selected').length;
                        if (selectedCount > 1) {
                            tagFilterList.querySelectorAll('.tag-filter.selected').forEach(button => {
                                button.classList.add('multi-selected');
                            });
                        } else {
                            tagFilterList.querySelectorAll('.tag-filter').forEach(button => {
                                button.classList.remove('multi-selected');
                            });
                        }
                    }
                    
                    filterChannelsByTag();
            }
        });
    }

    // Event listener for refresh button
    if (refreshButton) {
        refreshButton.addEventListener('click', async () => {
            refreshStatus.textContent = 'Refreshing... please wait.';
            refreshStatus.className = '';
            refreshButton.disabled = true;

            try {
                const response = await fetch('/refresh_from_youtube', { method: 'POST' });
                const result = await response.json();

                if (response.ok && result.success) {
                    refreshStatus.textContent = result.message || 'Refresh successful!';
                    refreshStatus.classList.add('success');
                    // Actualizar datos globales y redibujar todo
                    window.tagColors = result.tag_colors;
                    updateChannelList(result.channels);
                    updateTagFilters(result.unique_tags);
                    // Reset filter visually and logically
                    tagFilterList.querySelectorAll('.tag-filter').forEach(button => button.classList.remove('active'));
                    tagFilterList.querySelector('.tag-filter[data-tag="all"]')?.classList.add('active');
                        filterChannelsByTag();
                } else {
                     throw new Error(result.message || 'Failed to refresh from YouTube.');
                }

            } catch (error) {
                console.error('Error refreshing subscriptions:', error);
                refreshStatus.textContent = `Error: ${error.message}`;
                refreshStatus.classList.add('error');
            } finally {
                refreshButton.disabled = false;
                setTimeout(() => {
                    refreshStatus.textContent = '';
                    refreshStatus.className = '';
                }, 5000);
            }
        });
    }

    // Event listeners for Interactive Tag List (Color Palette)
    if (interactiveTagList) {
        // Listener para MOSTRAR/OCULTAR paleta
        interactiveTagList.addEventListener('click', (event) => {
            if (event.target.classList.contains('tag-clickable')) {
                const palette = event.target.nextElementSibling;
                if (palette && palette.classList.contains('color-palette')) {
                    interactiveTagList.querySelectorAll('.color-palette:not(.hidden)')
                        .forEach(p => { if (p !== palette) p.classList.add('hidden'); });
                    palette.classList.toggle('hidden');
                }
                 // Ocultar la paleta si se hace clic fuera de ella o del tag
                 document.addEventListener('click', hidePaletteOnClickOutside, { once: true, capture: true });
            }
        }, true); // Use capture phase maybe? Or handle outside click better. Let's try basic first.

        // Listener para SELECCIONAR color
        interactiveTagList.addEventListener('click', async (event) => {
            if (event.target.classList.contains('color-option')) {
                event.stopPropagation(); // Prevent click from bubbling up to the toggle listener immediately
                const button = event.target;
                const newColor = button.dataset.color;
                const tagEntry = button.closest('.tag-entry');
                const tagSpan = tagEntry?.querySelector('.tag-display');
                const tag = tagSpan?.dataset.tag;
                const palette = button.closest('.color-palette');

                if (!tag || !newColor || !palette) return;

                palette.classList.add('hidden'); // Ocultar paleta

                if (getTagColor(tag) === newColor) return; // No hacer nada si el color es el mismo

                try {
                    const response = await fetch(`/api/tags/color/${encodeURIComponent(tag)}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ color: newColor }),
                    });
                    const result = await response.json();

                    if (response.ok && result.success) {
                        window.tagColors = result.all_colors; // Actualizar mapa global
                        updateTagColorOnPage(tag, newColor); // Actualizar UI
                    } else {
                        throw new Error(result.message || 'Failed to update color');
                    }
                } catch (error) {
                    console.error(`Error updating color for tag ${tag}:`, error);
                    alert(`Error updating color: ${error.message}`); // Informar al usuario
                }
            }
        });
    }

     // Helper to hide palettes when clicking outside
     function hidePaletteOnClickOutside(event) {
        if (!interactiveTagList) return;
         const openPalette = interactiveTagList.querySelector('.color-palette:not(.hidden)');
         if (openPalette && !openPalette.contains(event.target) && !openPalette.previousElementSibling.contains(event.target)) {
             openPalette.classList.add('hidden');
         } else if (openPalette) {
             // Re-attach listener if click was inside but didn't close it (e.g. on palette bg)
             document.addEventListener('click', hidePaletteOnClickOutside, { once: true, capture: true });
         }
     }
    }

    // Initial filter application (show all)
    filterChannelsByTag();

    // Add this after the existing event listeners
    searchInput.addEventListener('input', function() {
        const searchText = this.value.toLowerCase();
        const channels = document.querySelectorAll('.channel-card');
        let visibleCount = 0;
        
        channels.forEach(channel => {
            const title = channel.querySelector('.channel-info h3 a').textContent.toLowerCase();
            const description = channel.querySelector('.channel-info .current-tags').textContent.toLowerCase();
            
            if (title.includes(searchText) || description.includes(searchText)) {
                channel.style.display = '';
                visibleCount++;
            } else {
                channel.style.display = 'none';
            }
        });
        
        channelCountSpan.textContent = visibleCount;
    });

}); // End of DOMContentLoaded

// --- NEW Helper function to update star visuals ---
function updateStarsVisual(ratingContainer, ratingValue) {
     if (!ratingContainer) return;
     const stars = ratingContainer.querySelectorAll('.star');
     const numericRating = ratingValue === null ? 0 : parseInt(ratingValue, 10);
     stars.forEach((star, index) => {
         if (index < numericRating) {
             star.classList.add('filled');
         } else {
             star.classList.remove('filled');
         }
     });

     // Add or remove the clear button based on the rating
     let clearButton = ratingContainer.querySelector('.clear-rating');
     if (numericRating > 0 && !clearButton) {
         clearButton = document.createElement('span');
         clearButton.className = 'clear-rating';
         clearButton.title = 'Clear rating';
         clearButton.innerHTML = '&#10006;'; // Simple X
         ratingContainer.appendChild(clearButton);
     } else if (numericRating === 0 && clearButton) {
         clearButton.remove();
     }
}
// --- END NEW Helper function ---
