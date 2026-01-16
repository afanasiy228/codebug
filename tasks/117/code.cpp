#include <bits/stdc++.h>
using namespace std;

long long dist(const pair<int,int> &a, const pair<int,int> &b) {
    return llabs(a.first - b.first) + llabs(a.second - b.second);
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
        return 0;
    }

    vector<pair<int,int>> p(n);
    for (int i = 0; i < n; i++) {
        cin >> p[i].first >> p[i].second;
    }

    vector<int> order;
    vector<char> used(n, false);
    order.push_back(0);
    used[0] = true;

    for (int step = 1; step < n; step++) {
        int last = order.back();
        long long best = (1LL << 60);
        int best_v = -1;
        for (int v = 0; v < n; v++) {
            if (used[v]) continue;
            long long d = dist(p[last], p[v]);
            if (d < best) {
                best = d;
                best_v = v;
            }
        }
        used[best_v] = true;
        order.push_back(best_v);
    }

    long long total = 0;
    for (int i = 0; i + 1 < n; i++) {
        total += dist(p[order[i]], p[order[i + 1]]);
    }
    total += dist(p[order.back()], p[order[0]]);

    cout << total << "
";
    return 0;
}
