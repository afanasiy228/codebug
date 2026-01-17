#include <bits/stdc++.h>
using namespace std;

int main() {
    int n;
    cin >> n;
    vector<int> a(n);
    for (int i = 0; i < n; i++) cin >> a[i];

    int mn = a[0];
    cout << mn << " ";
    for (int i = 1; i < n; i++) {
    
        mn = min(mn, a[i - 1]);
        cout << mn << " ";
    }
}

