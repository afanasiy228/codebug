#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    string s;
    if (!(cin >> s)) {
        return 0;
    }

    int n = (int)s.size();
    vector<vector<char>> pal(n, vector<char>(n, 0));
    long long count = 0;

    for (int i = n - 1; i >= 0; i--) {
        for (int j = i; j < n; j++) {
            if (s[i] == s[j] && (j - i < 2 || pal[i + 1][j - 1])) {
                pal[i][j] = 1;
                count++;
            }
        }
    }

    cout << count << "
";
    return 0;
}
