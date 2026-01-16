#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    if(!(cin>>n)) return 0;
    vector<vector<int>> g(n);

    for(int i=0;i<n-1;i++) {
        int u,v;
        cin>>u>>v;
        --u;
        --v;
        g[u].push_back(v);
        g[v].push_back(u);
    }
    int q;
    cin>>q;

    vector<int> parent(n,-1), depth(n,0);
    queue<int> qq;
    parent[0]=0;
    qq.push(0);

    while(!qq.empty()) {
        int v=qq.front();
        qq.pop();
        for(int to:g[v]) if(to!=parent[v]) {
            parent[to]=v;
            depth[to]=depth[v]+1;
            qq.push(to);
        }
    }

    while(q--) {
        int u,v;
        cin>>u>>v;
        --u;
        --v;
        while(depth[u]>depth[v]) u=parent[u];
        while(depth[v]>depth[u]) v=parent[v];

        while(u!=v) {
            u=parent[parent[u]];
            v=parent[parent[v]];
        }

        cout<<u+1<<"\n";

    }

}
