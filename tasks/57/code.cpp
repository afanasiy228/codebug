#include <bits/stdc++.h>
using namespace std;

struct DSU {
    vector<int> p, sz;
    DSU(int n):p(n+1),sz(n+1,1) {
        iota(p.begin(),p.end(),0);
    }
    int f(int x) {
        return p[x]==x?x:p[x]=f(p[x]);
    }

    void u(int a,int b) {
        a=f(a);
        b=f(b);
        if(a!=b) {
            p[b]=a;
            sz[a]+=sz[b];
        }
    }
}
;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,q;
    if(!(cin>>n>>q)) return 0;
    DSU d(n);

    while(q--) {
        string op;
        cin>>op;
        if(op=="union") {
            int a,b;
            cin>>a>>b;
            d.u(a,b);
        }
        else  {
            int a;
            cin>>a;
            cout<<d.sz[a]<<"\n";
        }
    }

}
