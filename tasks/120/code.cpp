#include <bits/stdc++.h>
using namespace std;

struct Hasher {
    const long long mod = 1000000007LL;
    const long long base = 911382323LL;
    vector<long long> pref, pows;

    Hasher(const string &s) {
        int n = (int)s.size();
        pref.assign(n + 1, 0);
        pows.assign(n + 1, 1);
        for (int i = 0; i < n; i++) {
            pref[i + 1] = (pref[i] * base + (s[i] + 1)) % mod;
            pows[i + 1] = (pows[i] * base) % mod;
        }
    }

    long long get(int l, int r) {
        long long res = (pref[r] - pref[l] * pows[r - l]) % mod;
        if (res < 0) res += mod;
        return res;
    }
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s;
    if (!(cin >> s)) {
        return 0;
    }

    int q;
    cin >> q;
    int n = (int)s.size();
    Hasher h(s);

    auto lcp = [&](int i, int j) {
        int lo = 0;
        int hi = n - max(i, j);
        while (lo < hi) {
            int mid = (lo + hi + 1) / 2;
            if (h.get(i, i + mid) == h.get(j, j + mid)) {
                lo = mid;
            } else {
                hi = mid - 1;
            }
        }
        return lo;
    };

    while (q--) {
        int i, j;
        cin >> i >> j;
        // ошибки в индексах: используем 1-based как 0-based
        cout << lcp(i, j) << "
";
    }

    return 0;
}
