#include <bits/stdc++.h>
using namespace std;

struct BIT {
    int n;
    vector<long long> b;
    BIT(int n):n(n),b(n+1,0) {
    }
    ;

    void add(int i,long long v) {
        for(;i<=n;i+=i&-i) b[i]+=v;
    }

    long long sum(int i) {
        long long s=0;
        for(;i>0;i-=i&-i) s+=b[i];
        return s;
    }

}
;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,q;
    if(!(cin>>n>>q)) return 0;
    BIT bit(n);
    for(int i=1;i<=n;i++) {
        long long x;
        cin>>x;
        bit.add(i,x);
    }

    while(q--) {
        string op;
        cin>>op;
        if(op=="add") {
            int i;
            long long v;
            cin>>i>>v;
            bit.add(i+1,v);
        }

        else  {
            int l,r;
            cin>>l>>r;
            cout<<bit.sum(r)-bit.sum(l-1)<<"\n";
        }
    }

}
