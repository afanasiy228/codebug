/* How much of the broken code a participant changed: lines and characters.
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

    // Changed blocks between sequences a and b (arrays or strings) as [removed, added] slices.
    function hunks(a, b) {
        let start = 0;
        while (start < a.length && start < b.length && a[start] === b[start]) start++;
        let endA = a.length, endB = b.length;
        while (endA > start && endB > start && a[endA - 1] === b[endB - 1]) { endA--; endB--; }
        a = a.slice(start, endA);
        b = b.slice(start, endB);
        const n = a.length, m = b.length;
        if (n === 0 || m === 0) return n || m ? [[a, b]] : [];
        if (n * m > MAX_CELLS) return [[a, b]];

        const lcs = [];
        for (let i = 0; i <= n; i++) lcs.push(new Int32Array(m + 1));
        for (let i = n - 1; i >= 0; i--) {
            const row = lcs[i], below = lcs[i + 1], ai = a[i];
            for (let j = m - 1; j >= 0; j--) {
                row[j] = ai === b[j] ? below[j + 1] + 1 : Math.max(below[j], row[j + 1]);
            }
        }

        const out = [];
        let i = 0, j = 0, hi = 0, hj = 0;
        while (i < n || j < m) {
            if (i < n && j < m && a[i] === b[j]) {
                if (hi < i || hj < j) out.push([a.slice(hi, i), b.slice(hj, j)]);
                i++; j++;
                hi = i; hj = j;
            } else if (j >= m || (i < n && lcs[i + 1][j] >= lcs[i][j + 1])) {
                i++;
            } else {
                j++;
            }
        }
        if (hi < n || hj < m) out.push([a.slice(hi), b.slice(hj)]);
        return out;
    }

    function cost(a, b) {
        let total = 0;
        hunks(a, b).forEach(([removed, added]) => {
            total += removed.length * added.length > MAX_CELLS
                ? removed.length + added.length
                : Math.max(removed.length, added.length);
        });
        return total;
    }

    function countChangedLines(before, after) {
        return cost(normalizeLines(before), normalizeLines(after));
    }

    function countChangedChars(before, after) {
        let total = 0;
        hunks(normalizeLines(before), normalizeLines(after)).forEach(([removed, added]) => {
            total += cost(removed.join("\n"), added.join("\n"));
        });
        return total;
    }

    window.codebugCountChangedLines = countChangedLines;
    window.codebugCountChangedChars = countChangedChars;
})();
