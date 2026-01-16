#include <bits/stdc++.h>
using namespace std;

struct State {
    int link = -1;
    int len = 0;
    map<char, int> next;
};

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s;
    if (!(cin >> s)) {
        return 0;
    }

    int n = (int)s.size();
    if (n <= 1) {
        cout << n << "\n";
        return 0;
    }
    vector<int> sa(n);
    iota(sa.begin(), sa.end(), 0);

    sort(sa.begin(), sa.end(), [&](int a, int b) {
        return s.substr(a) < s.substr(b);
    });

    vector<int> lcp(n, 0);
    for (int i = 1; i < n; i++) {
        int a = sa[i - 1];
        int b = sa[i];
        int len = 0;
        while (a + len < n && b + len < n && s[a + len] == s[b + len]) {
            len++;
        }
        lcp[i] = len;
    }

    long long total = 1LL * n * (n - 1) / 2;
    long long sum_lcp = 0;
    for (int i = 1; i < n; i++) sum_lcp += lcp[i];

    cout << (total - sum_lcp) << "
";
    return 0;
}
