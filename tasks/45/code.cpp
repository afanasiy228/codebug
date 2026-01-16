#include <bits/stdc++.h>
using namespace std;

int n;
vector<vector<int>> g;
vector<int> sz;

int dfs(int v, int p) {
    int s=0;
    for(int to:g[v]) if(to!=p) s+=dfs(to,v);
    sz[v]=s;
    return s;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    if(!(cin>>n)) return 0;
    g.assign(n, {
    }
    );
    sz.assign(n,0);

    for(int i=0;i<n-1;i++) {
        int u,v;
        cin>>u>>v;
        --u;
        --v;
        g[u].push_back(v);
        g[v].push_back(u);
    }
    dfs(0,-1);

    for(int i=0;i<n;i++) {
        if(i) cout<<" ";
        cout<<sz[i];
    }
    cout<<"\n";

}
