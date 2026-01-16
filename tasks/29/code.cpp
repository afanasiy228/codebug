#include <bits/stdc++.h>
using namespace std;

struct DSU {
    vector<int> p,s;
    DSU(int n):p(n),s(n,1) {
        iota(p.begin(),p.end(),0);
    }
    int f(int x) {
        return p[x]==x?x:p[x]=f(p[x]);
    }

    bool u(int a,int b) {
        a=f(a);
        b=f(b);
        if(a==b) return false;
        if(s[a]<s[b]) swap(a,b);
        p[b]=a;
        s[a]+=s[b];
        return true;
    }
}

;
int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,m;
    if(!(cin>>n>>m)) return 0;
    vector<tuple<int,int,int>> e(m);

    for(int i=0;i<m;i++) {
        int u,v,w;
        cin>>u>>v>>w;
        --u;
        --v;
        e[i]=make_tuple(w,u,v);
    }

    sort(e.rbegin(), e.rend());

    DSU d(n);
    long long total=0;
    for(auto [w,u,v]:e) if(d.u(u,v)) total+=w;
    cout<<total<<"\n";

}
