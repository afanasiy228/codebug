#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,m,e;
    if(!(cin>>n>>m>>e)) return 0;
    vector<vector<int>> g(n);

    for(int i=0;i<e;i++) {
        int u,v;
        cin>>u>>v;
        --u;
        --v;
        g[u].push_back(v);
    }
    vector<int> match(m,-1);
    int ans=0;

    for(int u=0;u<n;u++) {
        for(int v: g[u]) if(match[v]==-1) {
            match[v]=u;
            ans++;
            break;
        }
    }

    cout<<ans<<"\n";

}
