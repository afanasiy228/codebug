#include <iostream>
#include <stack>
#include <queue>
#include <vector>

using namespace std;

vector<int> p;
vector<vector<int> > g;

vector<int> bfs(int s) {
  vector<int> dist(10000, 1e9);
  p.resize(10000, -1);
  dist[s] = 0;
  queue<int> q;
  q.push(s);

  while (!q.empty() ) {
    int v = q.front();
    q.pop();
    for (int u : g[v]) {
      if (dist[u] > dist[v] + 1) {
        dist[u] = dist[v] + 1;
        q.push(u);
        p[u] = v;
      }
    }
  }
  return dist;
}


void solve() {
  
  int s,t;
  cin >> s >> t;

  g.resize(10000);

  for (int i = 1000; i < 10000; i++) {
    if (i < 9000) g[i].push_back(i + 1000);
    if (i % 10 > 0) g[i].push_back(i - 1);
    g[i].push_back( ( (i % 10) * 1000) + i / 10);
    g[i].push_back( ( (i * 10) % 10000) + i / 1000);
  }
  
 

  auto d = bfs(s)[t];



  vector<int> ans;
  for (int v = t; v != -1; v = p[v]) {
    ans.push_back(v);
  }
  reverse(ans.begin(), ans.end());

  for (auto el : ans) cout << el << '\n';
}

int main(){
  int uwu = 1;
  // cin >> uwu;
  while (uwu --> 0) solve();
}