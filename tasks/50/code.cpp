#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,q;
    if(!(cin>>n>>q)) return 0;
    vector<long long>a(n+1);
    for(int i=1;i<=n;i++) cin>>a[i];

    vector<long long> pref(n+1,0);
    for(int i=1;i<=n;i++) pref[i]=pref[i-1]^a[i];

    while(q--) {
        int l,r;
        cin>>l>>r;
        cout<<(pref[r-1]^pref[l-1])<<"\n";
    }

}
