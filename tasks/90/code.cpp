#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s, p;
    if (!(cin >> s)) {
        return 0;
    }
    cin >> p;

    long long cnt = 0;
    for (size_t i = 0; i + p.size() <= s.size(); i++) {
        bool ok = true;
        for (size_t j = 0; j < p.size(); j++) {
            if (s[i + j] != p[j]) {
                ok = false;
                break;
            }
        }
        if (ok) {
            cnt++;
        }
    }

    cout << cnt << "
";
    return 0;
}
