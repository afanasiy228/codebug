#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if(!(cin>>n)) return 0;
    vector<long long>a(n);
    for(int i=0;i<n;i++) cin>>a[i];

    vector<long long> d;

    for(long long x: a) {

        auto it = upper_bound(d.begin(), d.end(), x);

        if(it==d.end()) d.push_back(x);
        else *it = x;

    }

    cout<<d.size()<<"\n";

}
