/* How many lines a participant changed in the broken code.
   Mirrors line_diff.py on the server line for line, so the counter in the
   editor and the server check always show the same number. */
(function () {
    const MAX_CELLS = 4000000;

    function normalizeLines(text) {
        const out = [];
        String(text || "").replace(/\r\n?/g, "\n").split("\n").forEach((raw) => {
            const line = raw.replace(/\s+/g, "");
            if (!line || line.startsWith("//")) return;
            out.push(line);
        });
        return out;
    }

    function countChangedLines(before, after) {
        let a = normalizeLines(before);
        let b = normalizeLines(after);
        let start = 0;
        while (start < a.length && start < b.length && a[start] === b[start]) start++;
        let endA = a.length, endB = b.length;
        while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) { endA--; endB--; }
        a = a.slice(start, endA);
        b = b.slice(start, endB);
        const n = a.length, m = b.length;
        if (n === 0 || m === 0) return Math.max(n, m);
        if (n * m > MAX_CELLS) return n + m;

        const lcs = [];
        for (let i = 0; i <= n; i++) lcs.push(new Int32Array(m + 1));
        for (let i = n - 1; i >= 0; i--) {
            const row = lcs[i], below = lcs[i + 1], ai = a[i];
            for (let j = m - 1; j >= 0; j--) {
                row[j] = ai === b[j] ? below[j + 1] + 1 : Math.max(below[j], row[j + 1]);
            }
        }

        let changed = 0, removed = 0, added = 0, i = 0, j = 0;
        while (i < n || j < m) {
            if (i < n && j < m && a[i] === b[j]) {
                changed += Math.max(removed, added);
                removed = 0; added = 0; i++; j++;
            } else if (j >= m || (i < n && lcs[i + 1][j] >= lcs[i][j + 1])) {
                removed++; i++;
            } else {
                added++; j++;
            }
        }
        return changed + Math.max(removed, added);
    }

    window.codebugCountChangedLines = countChangedLines;
})();
