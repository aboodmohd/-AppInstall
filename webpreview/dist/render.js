const STAR = 'M12 3.6l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8L3.5 9.8l5.9-.9L12 3.6z';
function element(tag, className) {
    const node = document.createElement(tag);
    node.className = className;
    return node;
}
/** A keyed list: rows are reused across renders, never rebuilt. */
export class AppListView {
    constructor(list, empty, count) {
        this.rows = new Map();
        this.entered = false;
        this.list = list;
        this.empty = empty;
        this.count = count;
    }
    render(apps) {
        const wanted = new Set(apps.map((app) => app.key));
        for (const [key, refs] of this.rows) {
            if (!wanted.has(key)) {
                refs.element.remove();
                this.rows.delete(key);
            }
        }
        let previous = null;
        apps.forEach((app, index) => {
            let refs = this.rows.get(app.key);
            if (!refs) {
                refs = this.createRow(app);
                this.rows.set(app.key, refs);
            }
            this.updateRow(refs, app);
            const expected = previous
                ? previous.nextElementSibling
                : this.list.firstElementChild;
            if (expected !== refs.element) {
                this.list.insertBefore(refs.element, expected);
            }
            previous = refs.element;
            // The entrance is one authored moment, and only for the first
            // render: later filter changes must not replay it.
            if (!this.entered) {
                refs.element.style.setProperty('--row-index', String(Math.min(index, 8)));
                refs.element.classList.add('app-row--enter');
            }
        });
        if (!this.entered) {
            this.entered = true;
        }
        this.count.textContent =
            apps.length === 1 ? '1 application' : `${apps.length} applications`;
        const isEmpty = apps.length === 0;
        this.empty.hidden = !isEmpty;
        this.list.hidden = isEmpty;
    }
    createRow(app) {
        const row = element('li', 'app-row');
        row.setAttribute('role', 'listitem');
        row.dataset.key = app.key;
        const icon = element('span', 'app-icon');
        const iconImage = element('img', 'app-icon-image');
        iconImage.alt = '';
        iconImage.loading = 'lazy';
        const iconInitial = element('span', 'app-initial');
        icon.append(iconImage, iconInitial);
        const body = element('span', 'app-body');
        const titleLine = element('span', 'app-title-line');
        const name = element('span', 'app-name');
        const chip = element('span', 'app-chip');
        const chipDot = element('span', 'app-chip-dot');
        const chipLabel = element('span', 'app-chip-label');
        chip.append(chipDot, chipLabel);
        titleLine.append(name, chip);
        const meta = element('span', 'app-meta');
        const problems = element('span', 'app-problems');
        problems.hidden = true;
        body.append(titleLine, meta, problems);
        const favorite = element('button', 'favorite');
        favorite.type = 'button';
        favorite.innerHTML =
            '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
                `<path d="${STAR}"/></svg>`;
        row.append(icon, body, favorite);
        this.list.append(row);
        return {
            element: row,
            iconImage,
            iconInitial,
            name,
            chip,
            chipLabel,
            meta,
            problems,
            favorite,
        };
    }
    updateRow(refs, app) {
        if (refs.name.textContent !== app.name) {
            refs.name.textContent = app.name;
        }
        const meta = [app.formatLabel];
        if (app.version && app.version !== 'unknown') {
            meta.push(app.version);
        }
        if (app.container) {
            meta.push(app.container);
        }
        meta.push(app.sizeText);
        const metaText = meta.join(' · ');
        if (refs.meta.textContent !== metaText) {
            refs.meta.textContent = metaText;
        }
        refs.chip.className = `app-chip app-chip--${app.statusTone}`;
        if (refs.chipLabel.textContent !== app.statusLabel) {
            refs.chipLabel.textContent = app.statusLabel;
        }
        if (app.problems) {
            refs.problems.hidden = false;
            refs.problems.textContent = app.problems;
        }
        else if (!refs.problems.hidden) {
            refs.problems.hidden = true;
            refs.problems.textContent = '';
        }
        const iconUrl = app.iconUrl;
        if (refs.iconImage.getAttribute('src') !== iconUrl) {
            if (iconUrl) {
                refs.iconImage.src = iconUrl;
                refs.iconImage.hidden = false;
                refs.iconInitial.hidden = true;
            }
            else {
                refs.iconImage.removeAttribute('src');
                refs.iconImage.hidden = true;
                refs.iconInitial.hidden = false;
            }
        }
        if (refs.iconInitial.textContent !== app.initial) {
            refs.iconInitial.textContent = app.initial;
        }
        refs.favorite.classList.toggle('favorite--on', app.favorite);
        refs.favorite.setAttribute('aria-pressed', app.favorite ? 'true' : 'false');
        refs.favorite.setAttribute('aria-label', app.favorite
            ? `Remove ${app.name} from favorites`
            : `Add ${app.name} to favorites`);
        refs.favorite.title = app.favorite ? 'Remove from favorites' : 'Add to favorites';
    }
}
/** A dropdown menu: the trigger button plus its popup panel. */
export class Dropdown {
    constructor(root, initial, onSelect) {
        const trigger = root.querySelector('.dropdown-trigger');
        const panel = root.querySelector('.dropdown-panel');
        if (!trigger || !panel) {
            throw new Error('a dropdown needs a trigger and a panel');
        }
        this.trigger = trigger;
        this.panel = panel;
        this.items = Array.from(panel.querySelectorAll('[role="menuitemradio"]'));
        this.onSelect = onSelect;
        this.value = initial;
        trigger.addEventListener('click', () => this.toggle());
        panel.addEventListener('click', (event) => {
            const target = event.target.closest('[role="menuitemradio"]');
            if (target) {
                this.choose(target.dataset.value ?? '');
            }
        });
        trigger.addEventListener('keydown', (event) => {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                this.open();
            }
        });
        panel.addEventListener('keydown', (event) => this.onPanelKey(event));
        document.addEventListener('click', (event) => {
            if (!this.panel.hidden && !root.contains(event.target)) {
                this.close();
            }
        });
        this.setValue(initial);
    }
    onPanelKey(event) {
        if (event.key === 'Escape') {
            event.preventDefault();
            this.close();
            this.trigger.focus();
            return;
        }
        if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') {
            return;
        }
        event.preventDefault();
        const current = this.items.indexOf(document.activeElement);
        const step = event.key === 'ArrowDown' ? 1 : -1;
        const next = (current + step + this.items.length) % this.items.length;
        this.items[next].focus();
    }
    setValue(value) {
        this.value = value;
        for (const item of this.items) {
            const active = item.dataset.value === value;
            item.setAttribute('aria-checked', active ? 'true' : 'false');
            item.classList.toggle('dropdown-item--active', active);
        }
        const label = this.items.find((item) => item.dataset.value === value);
        if (label) {
            this.trigger.textContent = label.textContent ?? '';
        }
    }
    getValue() {
        return this.value;
    }
    choose(value) {
        this.setValue(value);
        this.close();
        this.trigger.focus();
        this.onSelect(value);
    }
    open() {
        this.panel.hidden = false;
        this.trigger.setAttribute('aria-expanded', 'true');
        const active = this.items.find((item) => item.dataset.value === this.value);
        (active ?? this.items[0])?.focus();
    }
    close() {
        this.panel.hidden = true;
        this.trigger.setAttribute('aria-expanded', 'false');
    }
    toggle() {
        if (this.panel.hidden) {
            this.open();
        }
        else {
            this.close();
        }
    }
}
