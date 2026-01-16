#include <bits/stdc++.h>
using namespace std;

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n,m;
    if(!(cin>>n>>m)) return 0;
    vector<vector<pair<int,int>>> g(n);

    for(int i=0;i<m;i++) {
        int u,v,w;
        cin>>u>>v>>w;
        --u;
        --v;
        g[u].push_back( {
            v,w
        }
        );
    }

    int s,t;
    cin>>s>>t;
    --s;
    --t;

    vector<int> dist(n,-1);
    queue<int> q;
    dist[s]=0;
    q.push(s);

    while(!q.empty()) {
        int v=q.front();
        q.pop();
        for(auto [to,w]:g[v]) if(dist[to]==-1) {
            dist[to]=dist[v]+1;
            q.push(to);
        }
    }

    cout<<dist[t]<<"\n";

}
