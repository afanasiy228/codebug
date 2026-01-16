#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,m;
    if(!(cin>>n>>m)) return 0;
    vector<vector<int>> g(n);

    for(int i=0;i<m;i++) {
        int u,v;
        cin>>u>>v;
        --u;
        --v;
        g[u].push_back(v);
        g[v].push_back(u);
    }

    vector<int> vis(n,0);

    function<bool(int,int)> dfs=[&](int v,int p) {
        vis[v]=1;
        for(int to:g[v]) if(to!=p) {
            if(vis[to]) return true;
            if(dfs(to,v)) return true;
        }
        return false;
    }
    ;

    bool cyc=false;
    for(int i=0;i<n;i++) if(!vis[i]) cyc|=dfs(i,-1);
    cout<<(cyc?"YES\n":"NO\n");

}
