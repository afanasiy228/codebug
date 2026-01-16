#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s;
    if (!(cin >> s)) {
        return 0;
    }

    string v = "aeiouy";
    int cnt = 0;
    for (char c : s) {
        if (v.find(c) != string::npos) {
            cnt++;
        }
    }

    cout << cnt << "\n";
    return 0;
}
