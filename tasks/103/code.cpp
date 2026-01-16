#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if (!(cin >> n)) {
        return 0;
    }

    int count = 0;
    for (int i = 2; i <= n; i++) {
        bool prime = true;
        for (int j = 2; j < i; j++) {
            if (i % j == 0) {
                prime = false;
                break;
            }
        }
        if (prime) {
            count++;
        }
    }

    cout << count << "
";
    return 0;
}
