#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,q;
    if(!(cin>>n>>q)) return 0;
    vector<long long>a(n);
    for(int i=0;i<n;i++) cin>>a[i];

    while(q--) {
        string op;
        cin>>op;
        if(op=="set") {
            int i;
            long long v;
            cin>>i>>v;
            a[i-1]=v;
        }
        else  {
            int l,r;
            cin>>l>>r;
            long long mx=LLONG_MIN;
            for(int i=l-1;i<r;i++) mx=max(mx,a[i]);
            cout<<mx<<"\n";
        }
    }

}
