#include <bits/stdc++.h>
using namespace std;

struct Point {
    long long x, y;
};

long long cross(const Point &o, const Point &a, const Point &b) {
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
        return 0;
    }

    vector<Point> pts(n);
    for (int i = 0; i < n; i++) {
        cin >> pts[i].x >> pts[i].y;
    }

    sort(pts.begin(), pts.end(), [](const Point &a, const Point &b) {
        if (a.x != b.x) return a.x < b.x;
        return a.y < b.y;
    });

    pts.erase(unique(pts.begin(), pts.end(), [](const Point &a, const Point &b) {
        return a.x == b.x && a.y == b.y;
    }), pts.end());

    if (pts.size() <= 1) {
        cout << fixed << setprecision(6) << 0.0 << "
";
        return 0;
    }

    vector<Point> lower, upper;
    for (const auto &p : pts) {
        while (lower.size() >= 2 && cross(lower[lower.size() - 2], lower.back(), p) <= 0) {
            lower.pop_back();
        }
        lower.push_back(p);
    }
    for (int i = (int)pts.size() - 1; i >= 0; i--) {
        Point p = pts[i];
        while (upper.size() >= 2 && cross(upper[upper.size() - 2], upper.back(), p) <= 0) {
            upper.pop_back();
        }
        upper.push_back(p);
    }

    vector<Point> hull = lower;
    for (size_t i = 1; i + 1 < upper.size(); i++) {
        hull.push_back(upper[i]);
    }

    long double per = 0.0;
    for (size_t i = 0; i < hull.size(); i++) {
        Point a = hull[i];
        Point b = hull[(i + 1) % hull.size()];
        long double dx = a.x - b.x;
        long double dy = a.y - b.y;
        per += dx * dx + dy * dy;
    }

    cout << fixed << setprecision(6) << (double)per << "
";
    return 0;
}
