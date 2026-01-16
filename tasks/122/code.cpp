#include <bits/stdc++.h>
using namespace std;

struct Line {
    long long m;
    long long b;
};

long double intersectX(const Line &a, const Line &b) {
    return (long double)(b.b - a.b) / (a.m - b.m);
}

long long value(const Line &l, long long x) {
    return l.m * x + l.b;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
        return 0;
    }

    vector<long long> x(n), a(n), b(n);
    for (int i = 0; i < n; i++) cin >> x[i];
    for (int i = 0; i < n; i++) cin >> a[i];
    for (int i = 0; i < n; i++) cin >> b[i];

    vector<long long> dp(n, 0);
    deque<Line> hull;

    hull.push_back({a[0], dp[0] + b[0]});

    int ptr = 0;
    for (int i = 1; i < n; i++) {
        while (hull.size() >= 2 && value(hull[0], x[i]) >= value(hull[1], x[i])) {
            hull.pop_front();
        }
        dp[i] = value(hull[0], x[i]);

        Line nl{a[i], dp[i] + b[i]};
        if (!hull.empty() && hull.back().m == nl.m) {
            if (hull.back().b <= nl.b) {
                hull.pop_back();
            } else {
                continue;
            }
        }
        while (hull.size() >= 2) {
            Line l1 = hull[hull.size() - 2];
            Line l2 = hull[hull.size() - 1];
            if (intersectX(l1, l2) >= intersectX(l2, nl)) {
                hull.pop_back();
            } else {
                break;
            }
        }
        hull.push_back(nl);
    }

    for (int i = 0; i < n; i++) {
        cout << dp[i] << "
";
    }
    return 0;
}
