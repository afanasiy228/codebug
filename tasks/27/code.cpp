#include <bits/stdc++.h>
using namespace std;

struct DSU {
    vector<int> p;
    DSU(int n):p(n) {
        iota(p.begin(),p.end(),0);
    }
    int find(int x) {
        return p[x]==x?x:p[x]=find(p[x]);
    }

    void unite(int a,int b) {
        a=find(a);
        b=find(b);
        if(a!=b) p[b]=a;
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
        int a,b;
        cin>>a>>b;
        --a;
        --b;
        if(op=="union") d.unite(a,b);
        else cout<<(a==b?"YES\n":"NO\n");
    }

}
