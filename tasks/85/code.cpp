#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string text, pattern;
    if (!(cin >> text >> pattern)) return 0;
    int n = text.size();
    int m = pattern.size();
    if (m > n) { cout << 0 << "\n"; return 0; }

    vector<int> need(26, 0), cur(26, 0);
    for (char c : pattern) need[c - 'a']++;
    for (int i = 0; i < m; ++i) cur[text[i] - 'a']++;

    int cnt = 0;
    if (cur == need) cnt++;
    for (int i = m; i < n; ++i) {
        cur[text[i] - 'a']++;
        cur[text[i - m] - 'a']--;
        if (cur == need) cnt++;
    }

    cout << cnt << "\n";
    return 0;
}
